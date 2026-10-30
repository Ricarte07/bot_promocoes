// Package application liga as portas: de onde vêm as promoções e para onde
// vão as notificações. Não conhece Redis nem Telegram.
package application

import (
	"context"
	"fmt"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

// Notificador é a porta de saída: Telegram hoje, outro canal amanhã.
type Notificador interface {
	Notificar(ctx context.Context, promocao domain.Promocao) error
}

// Tratador é o que a fila chama para cada promoção recebida.
// Devolver erro significa "não confirme a mensagem, tente de novo depois".
type Tratador func(ctx context.Context, promocao domain.Promocao) error

// FonteDePromocoes é a porta de entrada: Redis Streams hoje.
// Executar bloqueia até o contexto ser cancelado.
type FonteDePromocoes interface {
	Executar(ctx context.Context, tratar Tratador) error
}

// NotificarPromocao é o caso de uso: valida e repassa ao notificador sobre as ofertas.
type NotificarPromocao struct {
	notificador Notificador
}

func NovoNotificarPromocao(notificador Notificador) *NotificarPromocao {
	return &NotificarPromocao{notificador: notificador}
}

func (uc *NotificarPromocao) Executar(ctx context.Context, promocao domain.Promocao) error {
	if err := promocao.Validar(); err != nil {
		return err
	}
	if err := uc.notificador.Notificar(ctx, promocao); err != nil {
		return fmt.Errorf("notificar %s/%s: %w", promocao.Loja, promocao.ProdutoID, err)
	}
	return nil
}
