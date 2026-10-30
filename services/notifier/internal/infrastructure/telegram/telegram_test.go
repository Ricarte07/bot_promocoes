package telegram

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

func promocaoExemplo() domain.Promocao {
	return domain.Promocao{
		ProdutoID:          "725571",
		Loja:               "kabum",
		Nome:               "Fonte Gamer Rise Mode Elektra, 650W",
		URL:                "https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w",
		PrecoAtual:         "279.99",
		PrecoFinal:         "265.99",
		PrecoReferencia:    "377.77",
		DescontoPercentual: "29.59",
		Cupom:              domain.Cupom{Codigo: "ESQUENTA", DescontoPercentual: "5.00"},
	}
}

// --- FormatarMensagem: função pura ------------------------------------------

func TestMensagemCompletaComCupom(t *testing.T) {
	esperado := "🔥 <b>Promoção na Kabum</b>\n" +
		"Fonte Gamer Rise Mode Elektra, 650W\n" +
		"De R$ 377,77 por <b>R$ 265,99</b> (29,59% de desconto)\n" +
		"🎟️ Cupom <code>ESQUENTA</code> (5,00% já aplicado no preço)\n" +
		`<a href="https://www.kabum.com.br/produto/725571/fonte-gamer-rise-mode-elektra-650w">Ver na loja</a>`

	if obtido := FormatarMensagem(promocaoExemplo()); obtido != esperado {
		t.Fatalf("mensagem diferente.\nesperado:\n%s\nobtido:\n%s", esperado, obtido)
	}
}

func TestMensagemComCupomDeValorDesconhecido(t *testing.T) {
	p := promocaoExemplo()
	p.Cupom = domain.Cupom{Codigo: "10DO10"}
	p.PrecoFinal = p.PrecoAtual

	obtido := FormatarMensagem(p)

	if !strings.Contains(obtido, "por <b>R$ 279,99</b>") {
		t.Errorf("sem valor do cupom o preço final é o da página: %q", obtido)
	}
	if !strings.Contains(obtido, "🎟️ Cupom <code>10DO10</code> na loja (desconto não informado)") {
		t.Errorf("linha do cupom desconhecido errada: %q", obtido)
	}
}

func TestMensagemSemCupomNaoTemLinhaDeCupom(t *testing.T) {
	p := promocaoExemplo()
	p.Cupom = domain.Cupom{}

	if obtido := FormatarMensagem(p); strings.Contains(obtido, "Cupom") {
		t.Errorf("sem cupom não deveria haver linha de cupom: %q", obtido)
	}
}

func TestMensagemSemNomeNemURLUsaIdESemLink(t *testing.T) {
	p := promocaoExemplo()
	p.Nome, p.URL = "", ""

	obtido := FormatarMensagem(p)

	if !strings.Contains(obtido, "produto 725571\n") {
		t.Errorf("deveria usar o id como título: %q", obtido)
	}
	if strings.Contains(obtido, "<a ") {
		t.Errorf("sem URL não deveria ter link: %q", obtido)
	}
}

func TestMensagemEscapaHTMLDoNomeEDoCupom(t *testing.T) {
	p := promocaoExemplo()
	p.Nome = `Cabo HDMI <2m> "premium" & cia`
	p.Cupom.Codigo = "<X>"

	obtido := FormatarMensagem(p)

	if !strings.Contains(obtido, "Cabo HDMI &lt;2m&gt; &#34;premium&#34; &amp; cia") {
		t.Errorf("nome deveria estar escapado: %q", obtido)
	}
	if !strings.Contains(obtido, "<code>&lt;X&gt;</code>") {
		t.Errorf("código do cupom deveria estar escapado: %q", obtido)
	}
}

func TestFormatarReal(t *testing.T) {
	casos := map[string]string{
		"901.55":     "R$ 901,55",
		"1099.90":    "R$ 1.099,90",
		"1000":       "R$ 1.000,00",
		"5699.99":    "R$ 5.699,99",
		"1234567.89": "R$ 1.234.567,89",
		"0.99":       "R$ 0,99",
	}
	for entrada, esperado := range casos {
		if obtido := formatarReal(entrada); obtido != esperado {
			t.Errorf("formatarReal(%q) = %q, esperava %q", entrada, obtido, esperado)
		}
	}
}

// --- Cliente: fala com um servidor falso -------------------------------------

type chamada struct {
	caminho string
	corpo   map[string]any
}

func servidorFalso(t *testing.T, status int, resposta string) (*httptest.Server, *[]chamada) {
	t.Helper()
	chamadas := &[]chamada{}
	servidor := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var corpo map[string]any
		if err := json.NewDecoder(r.Body).Decode(&corpo); err != nil {
			t.Errorf("corpo não é JSON: %v", err)
		}
		*chamadas = append(*chamadas, chamada{caminho: r.URL.Path, corpo: corpo})
		w.WriteHeader(status)
		_, _ = w.Write([]byte(resposta))
	}))
	t.Cleanup(servidor.Close)
	return servidor, chamadas
}

func TestEnviaSendMessageComTokenChatEHTML(t *testing.T) {
	servidor, chamadas := servidorFalso(t, http.StatusOK, `{"ok":true,"result":{}}`)
	cliente := NovoCliente("123:ABC", "-100777", ComURLBase(servidor.URL))

	if err := cliente.Notificar(context.Background(), promocaoExemplo()); err != nil {
		t.Fatalf("erro inesperado: %v", err)
	}

	if len(*chamadas) != 1 {
		t.Fatalf("esperava 1 chamada, houve %d", len(*chamadas))
	}
	c := (*chamadas)[0]
	if c.caminho != "/bot123:ABC/sendMessage" {
		t.Errorf("caminho errado: %s", c.caminho)
	}
	if c.corpo["chat_id"] != "-100777" || c.corpo["parse_mode"] != "HTML" {
		t.Errorf("corpo errado: %+v", c.corpo)
	}
	if texto, _ := c.corpo["text"].(string); !strings.Contains(texto, "R$ 265,99") {
		t.Errorf("texto não tem o preço final: %q", texto)
	}
}

func TestErroDaAPIViraErroComDescricao(t *testing.T) {
	servidor, _ := servidorFalso(t, http.StatusBadRequest,
		`{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}`)
	cliente := NovoCliente("123:ABC", "0", ComURLBase(servidor.URL))

	err := cliente.Notificar(context.Background(), promocaoExemplo())

	if err == nil || !strings.Contains(err.Error(), "chat not found") {
		t.Fatalf("esperava erro com a descrição da API, veio %v", err)
	}
}

func TestServidorForaDoArViraErro(t *testing.T) {
	servidor, _ := servidorFalso(t, http.StatusOK, `{"ok":true}`)
	servidor.Close()
	cliente := NovoCliente("123:ABC", "0", ComURLBase(servidor.URL))

	if err := cliente.Notificar(context.Background(), promocaoExemplo()); err == nil {
		t.Fatal("esperava erro de conexão")
	}
}
