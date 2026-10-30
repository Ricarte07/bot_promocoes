package queue

import (
	"context"
	"errors"
	"log/slog"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/application"
)

const (
	StreamPadrao = "promocoes"
	GrupoPadrao  = "notifier"
)

// Consumidor implementa application.FonteDePromocoes sobre Redis Streams.
//
// Usa um consumer group para que o Redis guarde o que ainda não foi
// confirmado: se o processo cair no meio, as mensagens pendentes são
// reentregues na próxima partida, antes das novas.
type Consumidor struct {
	cliente  *redis.Client
	log      *slog.Logger
	stream   string
	grupo    string
	nome     string
	bloqueio time.Duration // quanto tempo cada leitura espera por mensagens novas
	lote     int64
}

type Opcao func(*Consumidor)

func ComStream(stream string) Opcao     { return func(c *Consumidor) { c.stream = stream } }
func ComGrupo(grupo string) Opcao       { return func(c *Consumidor) { c.grupo = grupo } }
func ComBloqueio(d time.Duration) Opcao { return func(c *Consumidor) { c.bloqueio = d } }

func NovoConsumidor(cliente *redis.Client, log *slog.Logger, opcoes ...Opcao) *Consumidor {
	c := &Consumidor{
		cliente:  cliente,
		log:      log,
		stream:   StreamPadrao,
		grupo:    GrupoPadrao,
		nome:     "notifier-1",
		bloqueio: 5 * time.Second,
		lote:     10,
	}
	for _, aplicar := range opcoes {
		aplicar(c)
	}
	return c
}

// Executar lê o stream até o contexto ser cancelado.
func (c *Consumidor) Executar(ctx context.Context, tratar application.Tratador) error {
	if err := c.garantirGrupo(ctx); err != nil {
		return err
	}
	c.log.Info("consumindo promoções", "stream", c.stream, "grupo", c.grupo)

	// "0" entrega o que ficou pendente para este consumidor numa execução
	// anterior; depois ">" passa a entregar só mensagens novas.
	proximoID := "0"
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}

		resultado, err := c.cliente.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    c.grupo,
			Consumer: c.nome,
			Streams:  []string{c.stream, proximoID},
			Count:    c.lote,
			Block:    c.bloqueio,
		}).Result()

		switch {
		case errors.Is(err, redis.Nil):
			continue // tempo de bloqueio esgotou sem mensagem nova
		case err != nil:
			if ctx.Err() != nil {
				return ctx.Err()
			}
			c.log.Error("falha ao ler o stream", "erro", err)
			if !esperar(ctx, time.Second) {
				return ctx.Err()
			}
			continue
		}

		recebidas := 0
		for _, stream := range resultado {
			for _, mensagem := range stream.Messages {
				recebidas++
				c.processar(ctx, mensagem, tratar)
			}
		}
		if proximoID == "0" && recebidas == 0 {
			proximoID = ">" // pendências esgotadas
		}
	}
}

func (c *Consumidor) processar(ctx context.Context, mensagem redis.XMessage, tratar application.Tratador) {
	promocao, err := DecodificarEvento(mensagem.Values)
	if err != nil {
		// Mensagem fora do contrato nunca vai ficar certa: confirma e segue.
		c.log.Warn("mensagem descartada", "id", mensagem.ID, "erro", err)
		c.confirmar(ctx, mensagem.ID)
		return
	}

	if err := tratar(ctx, promocao); err != nil {
		// Sem ACK: fica pendente e volta na próxima partida do notifier.
		c.log.Error("promoção não notificada", "id", mensagem.ID, "erro", err)
		return
	}

	c.log.Info("promoção notificada", "id", mensagem.ID, "loja", promocao.Loja, "produto", promocao.ProdutoID)
	c.confirmar(ctx, mensagem.ID)
}

func (c *Consumidor) confirmar(ctx context.Context, id string) {
	if err := c.cliente.XAck(ctx, c.stream, c.grupo, id).Err(); err != nil {
		c.log.Error("falha ao confirmar mensagem", "id", id, "erro", err)
	}
}

// garantirGrupo cria o consumer group a partir das mensagens novas ("$").
// Rodar de novo com o grupo já criado não é erro.
func (c *Consumidor) garantirGrupo(ctx context.Context) error {
	err := c.cliente.XGroupCreateMkStream(ctx, c.stream, c.grupo, "$").Err()
	if err != nil && !strings.HasPrefix(err.Error(), "BUSYGROUP") {
		return err
	}
	return nil
}

func esperar(ctx context.Context, d time.Duration) bool {
	select {
	case <-ctx.Done():
		return false
	case <-time.After(d):
		return true
	}
}
