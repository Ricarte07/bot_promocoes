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
		ProdutoID:          "8776497",
		Loja:               "americanas",
		Nome:               "Impressora Epson EcoTank L1250 Wi-Fi Bivolt",
		URL:                "https://www.americanas.com.br/impressora-epson-8776497/p",
		PrecoAtual:         "901.55",
		PrecoReferencia:    "1099.90",
		DescontoPercentual: "18.04",
	}
}

// --- FormatarMensagem: função pura ------------------------------------------

func TestMensagemCompleta(t *testing.T) {
	esperado := "🔥 <b>Promoção na Americanas</b>\n" +
		"Impressora Epson EcoTank L1250 Wi-Fi Bivolt\n" +
		"De R$ 1.099,90 por <b>R$ 901,55</b> (18,04% de desconto)\n" +
		`<a href="https://www.americanas.com.br/impressora-epson-8776497/p">Ver na loja</a>`

	if obtido := FormatarMensagem(promocaoExemplo()); obtido != esperado {
		t.Fatalf("mensagem diferente.\nesperado:\n%s\nobtido:\n%s", esperado, obtido)
	}
}

func TestMensagemSemNomeNemURLUsaIdESemLink(t *testing.T) {
	p := promocaoExemplo()
	p.Nome, p.URL = "", ""

	obtido := FormatarMensagem(p)

	if !strings.Contains(obtido, "produto 8776497\n") {
		t.Errorf("deveria usar o id como título: %q", obtido)
	}
	if strings.Contains(obtido, "<a ") {
		t.Errorf("sem URL não deveria ter link: %q", obtido)
	}
}

func TestMensagemEscapaHTMLDoNome(t *testing.T) {
	p := promocaoExemplo()
	p.Nome = `Cabo HDMI <2m> "premium" & cia`

	obtido := FormatarMensagem(p)

	if !strings.Contains(obtido, "Cabo HDMI &lt;2m&gt; &#34;premium&#34; &amp; cia") {
		t.Errorf("nome deveria estar escapado: %q", obtido)
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
	if texto, _ := c.corpo["text"].(string); !strings.Contains(texto, "R$ 901,55") {
		t.Errorf("texto não tem o preço: %q", texto)
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
