package application

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

// ValidadePadraoIdempotencia é por quanto tempo a mesma promoção, pelo mesmo
// preço e cupom, não é anunciada de novo. Depois disso, se continuar valendo,
// o grupo é lembrado.
const ValidadePadraoIdempotencia = 7 * 24 * time.Hour

// RegistroDeEnvios é a porta onde o notifier lembra o que já mandou.
type RegistroDeEnvios interface {
	JaEnviado(ctx context.Context, chave string) (bool, error)
	MarcarEnviado(ctx context.Context, chave string, validade time.Duration) error
}

// NotificadorIdempotente é um Decorator: embrulha outro Notificador e garante
// que a mesma promoção não seja enviada duas vezes dentro da validade, mesmo
// que o evento chegue repetido (scraper reiniciado, mensagem reentregue pelo
// Redis depois de uma queda). O Notificador embrulhado não muda nada.
//
// Limite conhecido: se o processo cair entre o envio e a marcação, a mensagem
// volta e é enviada de novo. A API do Telegram não aceita chave de
// idempotência, então essa janela de milissegundos não tem como fechar.
type NotificadorIdempotente struct {
	proximo  Notificador
	registro RegistroDeEnvios
	validade time.Duration
	log      *slog.Logger
}

func NovoNotificadorIdempotente(
	proximo Notificador, registro RegistroDeEnvios, validade time.Duration, log *slog.Logger,
) *NotificadorIdempotente {
	return &NotificadorIdempotente{proximo: proximo, registro: registro, validade: validade, log: log}
}

func (n *NotificadorIdempotente) Notificar(ctx context.Context, promocao domain.Promocao) error {
	chave := promocao.ChaveIdempotencia()

	enviado, err := n.registro.JaEnviado(ctx, chave)
	if err != nil {
		// Sem saber se já foi, não envia: a mensagem fica pendente e é tentada depois.
		return fmt.Errorf("consultar envios anteriores: %w", err)
	}
	if enviado {
		n.log.Info("promoção já anunciada; repetição ignorada", "chave", chave)
		return nil
	}

	if err := n.proximo.Notificar(ctx, promocao); err != nil {
		return err // não marca: a mensagem não saiu
	}

	if err := n.registro.MarcarEnviado(ctx, chave, n.validade); err != nil {
		// A mensagem já saiu. Devolver erro deixaria ela pendente e ela seria
		// enviada de novo, que é justamente o que este Decorator evita.
		n.log.Warn("enviada, mas não registrada; uma repetição pode passar", "chave", chave, "erro", err)
	}
	return nil
}
