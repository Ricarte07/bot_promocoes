package domain

import (
	"errors"
	"testing"
)

func valida() Promocao {
	return Promocao{ProdutoID: "1", Loja: "kabum", PrecoAtual: "800.00", PrecoReferencia: "1000.00"}
}

func TestPromocaoValida(t *testing.T) {
	if err := valida().Validar(); err != nil {
		t.Fatalf("erro inesperado: %v", err)
	}
}

func TestPromocaoSemCamposObrigatoriosEInvalida(t *testing.T) {
	casos := map[string]func(*Promocao){
		"sem produto_id":       func(p *Promocao) { p.ProdutoID = "" },
		"sem loja":             func(p *Promocao) { p.Loja = "" },
		"sem preco_atual":      func(p *Promocao) { p.PrecoAtual = "" },
		"sem preco_referencia": func(p *Promocao) { p.PrecoReferencia = "" },
	}
	for nome, quebrar := range casos {
		p := valida()
		quebrar(&p)
		if err := p.Validar(); !errors.Is(err, ErrPromocaoInvalida) {
			t.Errorf("%s: esperava ErrPromocaoInvalida, veio %v", nome, err)
		}
	}
}

func TestTituloUsaNomeOuId(t *testing.T) {
	p := valida()
	if p.Titulo() != "produto 1" {
		t.Errorf("sem nome deveria usar o id, veio %q", p.Titulo())
	}
	p.Nome = "Notebook X"
	if p.Titulo() != "Notebook X" {
		t.Errorf("com nome deveria usar o nome, veio %q", p.Titulo())
	}
}
