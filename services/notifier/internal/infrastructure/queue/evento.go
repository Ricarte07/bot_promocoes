// Package queue lê promoções do Redis Stream `promocoes`, no formato de
// docs/evento-promocao.md, e as entrega ao caso de uso.
package queue

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

const (
	TipoEvento   = "promocao_detectada"
	VersaoEvento = 1
	CampoJSON    = "json"
)

// eventoPromocao espelha o JSON do contrato. Preços ficam como string de propósito.
type eventoPromocao struct {
	Tipo               string `json:"tipo"`
	Versao             int    `json:"versao"`
	ProdutoID          string `json:"produto_id"`
	Loja               string `json:"loja"`
	Nome               string `json:"nome"`
	URL                string `json:"url"`
	PrecoAtual         string `json:"preco_atual"`
	PrecoReferencia    string `json:"preco_referencia"`
	DescontoPercentual string `json:"desconto_percentual"`
	OcorridoEm         string `json:"ocorrido_em"`
}

// DecodificarEvento converte o campo `json` de uma entrada do stream em Promocao.
// Um erro aqui significa que a mensagem não segue o contrato e não adianta tentar de novo.
func DecodificarEvento(campos map[string]any) (domain.Promocao, error) {
	bruto, ok := campos[CampoJSON].(string)
	if !ok || bruto == "" {
		return domain.Promocao{}, fmt.Errorf("entrada sem o campo %q", CampoJSON)
	}

	var evento eventoPromocao
	if err := json.Unmarshal([]byte(bruto), &evento); err != nil {
		return domain.Promocao{}, fmt.Errorf("json inválido: %w", err)
	}
	if evento.Tipo != TipoEvento {
		return domain.Promocao{}, fmt.Errorf("tipo %q, esperava %q", evento.Tipo, TipoEvento)
	}
	if evento.Versao != VersaoEvento {
		return domain.Promocao{}, fmt.Errorf("versão %d, esperava %d", evento.Versao, VersaoEvento)
	}

	ocorridoEm, err := time.Parse(time.RFC3339Nano, evento.OcorridoEm)
	if err != nil {
		return domain.Promocao{}, fmt.Errorf("ocorrido_em %q: %w", evento.OcorridoEm, err)
	}

	promocao := domain.Promocao{
		ProdutoID:          evento.ProdutoID,
		Loja:               evento.Loja,
		Nome:               evento.Nome,
		URL:                evento.URL,
		PrecoAtual:         evento.PrecoAtual,
		PrecoReferencia:    evento.PrecoReferencia,
		DescontoPercentual: evento.DescontoPercentual,
		OcorridoEm:         ocorridoEm,
	}
	if err := promocao.Validar(); err != nil {
		return domain.Promocao{}, err
	}
	return promocao, nil
}
