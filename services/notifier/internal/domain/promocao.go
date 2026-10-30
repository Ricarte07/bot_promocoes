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

// Promocao é uma queda de preço detectada pelo scraper em uma loja.
type Promocao struct {
	ProdutoID          string
	Loja               string
	Nome               string // pode vir vazio; use ProdutoID como fallback ao exibir
	URL                string // pode vir vazio
	PrecoAtual         string // decimal com ponto, ex.: "901.55"
	PrecoReferencia    string
	DescontoPercentual string // ex.: "18.04"
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
