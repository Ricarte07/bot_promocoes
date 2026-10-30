package queue

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"strings"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

// Mesmo exemplo de docs/evento-promocao.md e do teste Python test_contrato_evento.py.
const eventoExemplo = `{"tipo": "promocao_detectada", "versao": 2, "produto_id": "725571", ` +
	`"loja": "kabum", "nome": "Fonte Gamer Rise Mode Elektra, 650W, Bronze, Full Modular", ` +
	`"url": "https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w", ` +
	`"preco_atual": "279.99", "preco_final": "265.99", "preco_referencia": "377.77", ` +
	`"desconto_percentual": "29.59", "cupom": {"codigo": "ESQUENTA", "desconto_percentual": "5.00"}, ` +
	`"ocorrido_em": "2026-10-30T17:54:35.380000+00:00"}`

// --- DecodificarEvento: função pura ------------------------------------------

func TestDecodificaEventoDoContrato(t *testing.T) {
	promocao, err := DecodificarEvento(map[string]any{"json": eventoExemplo})
	if err != nil {
		t.Fatalf("erro inesperado: %v", err)
	}

	esperado := domain.Promocao{
		ProdutoID:          "725571",
		Loja:               "kabum",
		Nome:               "Fonte Gamer Rise Mode Elektra, 650W, Bronze, Full Modular",
		URL:                "https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w",
		PrecoAtual:         "279.99",
		PrecoFinal:         "265.99",
		PrecoReferencia:    "377.77",
		DescontoPercentual: "29.59",
		Cupom:              domain.Cupom{Codigo: "ESQUENTA", DescontoPercentual: "5.00"},
		OcorridoEm:         time.Date(2026, 10, 30, 17, 54, 35, 380000000, time.UTC),
	}
	if !promocao.OcorridoEm.Equal(esperado.OcorridoEm) {
		t.Errorf("ocorrido_em = %v, esperava %v", promocao.OcorridoEm, esperado.OcorridoEm)
	}
	promocao.OcorridoEm, esperado.OcorridoEm = time.Time{}, time.Time{}
	if promocao != esperado {
		t.Errorf("promoção = %+v, esperava %+v", promocao, esperado)
	}
}

func TestCupomNuloEPercentualNulo(t *testing.T) {
	semCupom := strings.Replace(eventoExemplo, `{"codigo": "ESQUENTA", "desconto_percentual": "5.00"}`, "null", 1)
	promocao, err := DecodificarEvento(map[string]any{"json": semCupom})
	if err != nil {
		t.Fatalf("erro inesperado: %v", err)
	}
	if promocao.Cupom.Existe() {
		t.Errorf("cupom null não deveria existir, veio %+v", promocao.Cupom)
	}

	semValor := strings.Replace(eventoExemplo, `"desconto_percentual": "5.00"}`, `"desconto_percentual": null}`, 1)
	promocao, err = DecodificarEvento(map[string]any{"json": semValor})
	if err != nil {
		t.Fatalf("erro inesperado: %v", err)
	}
	if !promocao.Cupom.Existe() || promocao.Cupom.ValorConhecido() {
		t.Errorf("cupom com percentual null deveria existir sem valor, veio %+v", promocao.Cupom)
	}
}

func TestRejeitaMensagensForaDoContrato(t *testing.T) {
	casos := map[string]map[string]any{
		"sem campo json":    {"outro": "x"},
		"json inválido":     {"json": "{isso nao e json"},
		"tipo errado":       {"json": strings.Replace(eventoExemplo, "promocao_detectada", "outro_evento", 1)},
		"versão antiga":     {"json": strings.Replace(eventoExemplo, `"versao": 2`, `"versao": 1`, 1)},
		"data inválida":     {"json": strings.Replace(eventoExemplo, "2026-10-30T17:54:35.380000+00:00", "ontem", 1)},
		"sem produto_id":    {"json": strings.Replace(eventoExemplo, `"produto_id": "725571"`, `"produto_id": ""`, 1)},
		"sem preco_final":   {"json": strings.Replace(eventoExemplo, `"preco_final": "265.99", `, "", 1)},
		"preço como número": {"json": strings.Replace(eventoExemplo, `"preco_atual": "279.99"`, `"preco_atual": 279.99`, 1)},
	}
	for nome, campos := range casos {
		if _, err := DecodificarEvento(campos); err == nil {
			t.Errorf("%s: esperava erro", nome)
		}
	}
}

// --- Consumidor: contra um Redis em memória -----------------------------------

type ambiente struct {
	redis      *miniredis.Miniredis
	cliente    *redis.Client
	consumidor *Consumidor
}

func montar(t *testing.T) ambiente {
	t.Helper()
	servidor := miniredis.RunT(t)
	cliente := redis.NewClient(&redis.Options{Addr: servidor.Addr()})
	t.Cleanup(func() { _ = cliente.Close() })
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	consumidor := NovoConsumidor(cliente, log, ComBloqueio(50*time.Millisecond))

	// O grupo é criado a partir de "$": só o que entrar depois dele é entregue.
	if err := consumidor.garantirGrupo(context.Background()); err != nil {
		t.Fatalf("criar grupo: %v", err)
	}
	return ambiente{redis: servidor, cliente: cliente, consumidor: consumidor}
}

func (a ambiente) publicar(t *testing.T, campos map[string]any) {
	t.Helper()
	if err := a.cliente.XAdd(context.Background(), &redis.XAddArgs{Stream: StreamPadrao, Values: campos}).Err(); err != nil {
		t.Fatalf("xadd: %v", err)
	}
}

func (a ambiente) pendentes(t *testing.T) int64 {
	t.Helper()
	p, err := a.cliente.XPending(context.Background(), StreamPadrao, GrupoPadrao).Result()
	if err != nil {
		t.Fatalf("xpending: %v", err)
	}
	return p.Count
}

// executar roda o consumidor por um tempo curto e devolve o que o tratador recebeu.
func (a ambiente) executar(t *testing.T, tratar func(domain.Promocao) error) []domain.Promocao {
	t.Helper()
	var recebidas []domain.Promocao
	ctx, cancelar := context.WithTimeout(context.Background(), 400*time.Millisecond)
	defer cancelar()

	err := a.consumidor.Executar(ctx, func(_ context.Context, p domain.Promocao) error {
		recebidas = append(recebidas, p)
		return tratar(p)
	})
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("esperava terminar pelo contexto, veio %v", err)
	}
	return recebidas
}

func TestEntregaPromocaoEConfirma(t *testing.T) {
	a := montar(t)
	a.publicar(t, map[string]any{"json": eventoExemplo})

	recebidas := a.executar(t, func(domain.Promocao) error { return nil })

	if len(recebidas) != 1 || recebidas[0].ProdutoID != "725571" {
		t.Fatalf("esperava 1 promoção, veio %+v", recebidas)
	}
	if n := a.pendentes(t); n != 0 {
		t.Errorf("mensagem confirmada não deveria ficar pendente, há %d", n)
	}
}

func TestMensagemForaDoContratoEDescartadaSemTravarAsSeguintes(t *testing.T) {
	a := montar(t)
	a.publicar(t, map[string]any{"json": "{isso nao e json"})
	a.publicar(t, map[string]any{"json": eventoExemplo})

	recebidas := a.executar(t, func(domain.Promocao) error { return nil })

	if len(recebidas) != 1 {
		t.Fatalf("esperava só a válida, veio %d", len(recebidas))
	}
	if n := a.pendentes(t); n != 0 {
		t.Errorf("a inválida deveria ter sido confirmada e descartada, há %d pendente(s)", n)
	}
}

func TestFalhaNoTratadorDeixaMensagemPendente(t *testing.T) {
	a := montar(t)
	a.publicar(t, map[string]any{"json": eventoExemplo})

	a.executar(t, func(domain.Promocao) error { return errors.New("telegram fora do ar") })

	if n := a.pendentes(t); n != 1 {
		t.Errorf("mensagem não notificada deveria ficar pendente, há %d", n)
	}
}

func TestPendentesSaoReentreguesNaProximaPartida(t *testing.T) {
	a := montar(t)
	a.publicar(t, map[string]any{"json": eventoExemplo})
	a.executar(t, func(domain.Promocao) error { return errors.New("falhou da primeira vez") })

	recebidas := a.executar(t, func(domain.Promocao) error { return nil })

	if len(recebidas) != 1 {
		t.Fatalf("a pendente deveria ser reentregue, veio %d", len(recebidas))
	}
	if n := a.pendentes(t); n != 0 {
		t.Errorf("depois de notificar não deveria haver pendente, há %d", n)
	}
}

func TestRodarDeNovoComGrupoJaCriadoNaoEErro(t *testing.T) {
	a := montar(t)
	if err := a.consumidor.garantirGrupo(context.Background()); err != nil {
		t.Fatalf("segunda criação do grupo falhou: %v", err)
	}
}
