package telegram

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

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

type respostaFalsa struct {
	status int
	corpo  string
}

// servidorFalso responde, em ordem, cada item de respostas; a última se repete.
func servidorFalso(t *testing.T, respostas ...respostaFalsa) (*httptest.Server, *[]chamada) {
	t.Helper()
	chamadas := &[]chamada{}
	servidor := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var corpo map[string]any
		if err := json.NewDecoder(r.Body).Decode(&corpo); err != nil {
			t.Errorf("corpo não é JSON: %v", err)
		}
		*chamadas = append(*chamadas, chamada{caminho: r.URL.Path, corpo: corpo})
		indice := len(*chamadas) - 1
		if indice >= len(respostas) {
			indice = len(respostas) - 1
		}
		w.WriteHeader(respostas[indice].status)
		_, _ = w.Write([]byte(respostas[indice].corpo))
	}))
	t.Cleanup(servidor.Close)
	return servidor, chamadas
}

var (
	ok200      = respostaFalsa{http.StatusOK, `{"ok":true,"result":{}}`}
	lotado429  = respostaFalsa{http.StatusTooManyRequests, `{"ok":false,"error_code":429,"description":"Too Many Requests: retry after 2","parameters":{"retry_after":2}}`}
	chatErrado = respostaFalsa{http.StatusBadRequest, `{"ok":false,"error_code":400,"description":"Bad Request: chat not found"}`}
)

// relogioFalso registra as esperas pedidas e avança a hora só quando o teste manda.
type relogioFalso struct {
	esperas []time.Duration
	hora    time.Time
}

func (r *relogioFalso) dormir(_ context.Context, d time.Duration) error {
	r.esperas = append(r.esperas, d)
	r.hora = r.hora.Add(d)
	return nil
}

func (r *relogioFalso) agora() time.Time { return r.hora }

func clienteDeTeste(t *testing.T, servidor *httptest.Server, opcoes ...Opcao) (*Cliente, *relogioFalso) {
	t.Helper()
	relogio := &relogioFalso{hora: time.Date(2026, 11, 3, 10, 0, 0, 0, time.UTC)}
	opcoes = append([]Opcao{ComURLBase(servidor.URL), ComRelogio(relogio.dormir, relogio.agora)}, opcoes...)
	return NovoCliente("123:ABC", "-100777", opcoes...), relogio
}

func TestEnviaSendMessageComTokenChatEHTML(t *testing.T) {
	servidor, chamadas := servidorFalso(t, ok200)
	cliente, _ := clienteDeTeste(t, servidor)

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

func TestEsperaOIntervaloEntreDoisEnviosMasNaoAntesDoPrimeiro(t *testing.T) {
	servidor, chamadas := servidorFalso(t, ok200)
	cliente, relogio := clienteDeTeste(t, servidor, ComIntervalo(time.Second))

	_ = cliente.Notificar(context.Background(), promocaoExemplo())
	_ = cliente.Notificar(context.Background(), promocaoExemplo())

	if len(*chamadas) != 2 {
		t.Fatalf("esperava 2 chamadas, houve %d", len(*chamadas))
	}
	if len(relogio.esperas) != 1 || relogio.esperas[0] != time.Second {
		t.Errorf("esperava uma única pausa de 1s entre os envios, veio %v", relogio.esperas)
	}
}

func TestNaoEsperaSeJaPassouOIntervalo(t *testing.T) {
	servidor, _ := servidorFalso(t, ok200)
	cliente, relogio := clienteDeTeste(t, servidor, ComIntervalo(time.Second))

	_ = cliente.Notificar(context.Background(), promocaoExemplo())
	relogio.hora = relogio.hora.Add(5 * time.Second) // o tempo passou por conta própria
	_ = cliente.Notificar(context.Background(), promocaoExemplo())

	if len(relogio.esperas) != 0 {
		t.Errorf("não deveria ter pausado, veio %v", relogio.esperas)
	}
}

func TestRespeitaRetryAfterDo429ETentaDeNovo(t *testing.T) {
	servidor, chamadas := servidorFalso(t, lotado429, ok200)
	cliente, relogio := clienteDeTeste(t, servidor, ComIntervalo(time.Second))

	if err := cliente.Notificar(context.Background(), promocaoExemplo()); err != nil {
		t.Fatalf("deveria ter conseguido na segunda tentativa: %v", err)
	}

	if len(*chamadas) != 2 {
		t.Errorf("esperava 2 chamadas, houve %d", len(*chamadas))
	}
	if len(relogio.esperas) != 1 || relogio.esperas[0] != 2*time.Second {
		t.Errorf("esperava pausa de 2s pedida pelo Telegram, veio %v", relogio.esperas)
	}
}

func TestDesisteDepoisDasTentativasConfiguradas(t *testing.T) {
	servidor, chamadas := servidorFalso(t, lotado429)
	cliente, _ := clienteDeTeste(t, servidor, ComTentativas(3))

	err := cliente.Notificar(context.Background(), promocaoExemplo())

	if err == nil || !strings.Contains(err.Error(), "429") {
		t.Fatalf("esperava erro 429 depois de desistir, veio %v", err)
	}
	if len(*chamadas) != 3 {
		t.Errorf("esperava 3 tentativas, houve %d", len(*chamadas))
	}
}

func TestContextoCanceladoDuranteAEsperaInterrompe(t *testing.T) {
	servidor, chamadas := servidorFalso(t, lotado429, ok200)
	cancelado := errors.New("cancelado")
	cliente := NovoCliente("123:ABC", "0", ComURLBase(servidor.URL),
		ComRelogio(func(context.Context, time.Duration) error { return cancelado }, time.Now))

	err := cliente.Notificar(context.Background(), promocaoExemplo())

	if !errors.Is(err, cancelado) {
		t.Fatalf("esperava o erro da espera, veio %v", err)
	}
	if len(*chamadas) != 1 {
		t.Errorf("não deveria ter tentado de novo, houve %d chamadas", len(*chamadas))
	}
}

func TestErroDaAPIViraErroComDescricao(t *testing.T) {
	servidor, _ := servidorFalso(t, chatErrado)
	cliente, _ := clienteDeTeste(t, servidor)

	err := cliente.Notificar(context.Background(), promocaoExemplo())

	if err == nil || !strings.Contains(err.Error(), "chat not found") {
		t.Fatalf("esperava erro com a descrição da API, veio %v", err)
	}
}

func TestServidorForaDoArViraErro(t *testing.T) {
	servidor, _ := servidorFalso(t, ok200)
	servidor.Close()
	cliente, _ := clienteDeTeste(t, servidor)

	if err := cliente.Notificar(context.Background(), promocaoExemplo()); err == nil {
		t.Fatal("esperava erro de conexão")
	}
}
