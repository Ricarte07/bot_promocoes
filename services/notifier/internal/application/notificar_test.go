package application

import (
	"context"
	"errors"
	"testing"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

type notificadorFalso struct {
	recebidas []domain.Promocao
	erro      error
}

func (n *notificadorFalso) Notificar(_ context.Context, p domain.Promocao) error {
	n.recebidas = append(n.recebidas, p)
	return n.erro
}

func promocaoValida() domain.Promocao {
	return domain.Promocao{
		ProdutoID:          "8776497",
		Loja:               "americanas",
		Nome:               "Impressora Epson",
		PrecoAtual:         "901.55",
		PrecoReferencia:    "1099.90",
		DescontoPercentual: "18.04",
	}
}

func TestRepassaPromocaoValidaAoNotificador(t *testing.T) {
	notificador := &notificadorFalso{}
	uc := NovoNotificarPromocao(notificador)

	if err := uc.Executar(context.Background(), promocaoValida()); err != nil {
		t.Fatalf("erro inesperado: %v", err)
	}
	if len(notificador.recebidas) != 1 || notificador.recebidas[0].ProdutoID != "8776497" {
		t.Fatalf("notificador deveria receber a promoção, recebeu %+v", notificador.recebidas)
	}
}

func TestPromocaoInvalidaNaoChegaAoNotificador(t *testing.T) {
	notificador := &notificadorFalso{}
	uc := NovoNotificarPromocao(notificador)

	err := uc.Executar(context.Background(), domain.Promocao{Loja: "kabum"})

	if !errors.Is(err, domain.ErrPromocaoInvalida) {
		t.Fatalf("esperava ErrPromocaoInvalida, veio %v", err)
	}
	if len(notificador.recebidas) != 0 {
		t.Fatal("promoção inválida não deveria ser notificada")
	}
}

func TestErroDoNotificadorEPropagado(t *testing.T) {
	falha := errors.New("telegram fora do ar")
	uc := NovoNotificarPromocao(&notificadorFalso{erro: falha})

	err := uc.Executar(context.Background(), promocaoValida())

	if !errors.Is(err, falha) {
		t.Fatalf("esperava o erro do notificador, veio %v", err)
	}
}
