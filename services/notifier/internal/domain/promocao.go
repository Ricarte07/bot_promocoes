// Package domain descreve o que o notifier entende por promoção.
//
// O notifier não faz conta com preço: só mostra. Por isso os valores ficam
// como texto decimal exato, do jeito que chegaram do scraper (ver
// docs/evento-promocao.md), em vez de float.
package domain

import (
	"errors"
	"time"
)

// Cupom é o cupom anunciado na página do produto. Codigo vazio significa
// "sem cupom". DescontoPercentual vazio significa que a loja mostra o
// código mas não diz quanto ele desconta.
type Cupom struct {
	Codigo             string
	DescontoPercentual string // ex.: "5.00"; vazio quando desconhecido
}

func (c Cupom) Existe() bool         { return c.Codigo != "" }
func (c Cupom) ValorConhecido() bool { return c.DescontoPercentual != "" }

// Promocao é uma queda de preço detectada pelo scraper em uma loja.
type Promocao struct {
	ProdutoID          string
	Loja               string
	Nome               string // pode vir vazio; use ProdutoID como fallback ao exibir
	URL                string // pode vir vazio
	PrecoAtual         string // preço "por" da página, sem cupom, ex.: "279.99"
	PrecoFinal         string // o que o comprador paga, com cupom aplicado
	PrecoReferencia    string // base do desconto: "de" da loja ou primeiro preço visto
	DescontoPercentual string // ex.: "29.59"
	Cupom              Cupom
	OcorridoEm         time.Time
}

var ErrPromocaoInvalida = errors.New("promoção inválida")

// Validar garante o mínimo para montar uma notificação útil.
func (p Promocao) Validar() error {
	switch {
	case p.ProdutoID == "":
		return errors.Join(ErrPromocaoInvalida, errors.New("produto_id vazio"))
	case p.Loja == "":
		return errors.Join(ErrPromocaoInvalida, errors.New("loja vazia"))
	case p.PrecoAtual == "":
		return errors.Join(ErrPromocaoInvalida, errors.New("preco_atual vazio"))
	case p.PrecoFinal == "":
		return errors.Join(ErrPromocaoInvalida, errors.New("preco_final vazio"))
	case p.PrecoReferencia == "":
		return errors.Join(ErrPromocaoInvalida, errors.New("preco_referencia vazio"))
	}
	return nil
}

// Titulo é o nome do produto ou, na falta dele, o id na loja.
func (p Promocao) Titulo() string {
	if p.Nome != "" {
		return p.Nome
	}
	return "produto " + p.ProdutoID
}
