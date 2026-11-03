// Package telegram envia mensagens pela Bot API usando só net/http.
//
// Um único endpoint nos interessa, sendMessage, então não vale uma
// biblioteca. A URL base é configurável para os testes apontarem para um
// servidor falso.
//
// O Telegram aceita cerca de uma mensagem por segundo no mesmo chat. Quando
// o scraper descobre uma listagem inteira, dezenas de promoções chegam de
// uma vez, por isso o cliente espera um intervalo mínimo entre envios e, se
// mesmo assim receber HTTP 429, respeita o retry_after da resposta e tenta
// de novo. Foi feito para um único consumidor sequencial, sem goroutines
// concorrentes chamando Notificar.
package telegram

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

const (
	URLBasePadrao    = "https://api.telegram.org"
	IntervaloPadrao  = 1100 * time.Millisecond // um pouco acima do limite de 1 msg/s do Telegram
	TentativasPadrao = 3
)

type Cliente struct {
	token       string
	chatID      string
	urlBase     string
	http        *http.Client
	intervalo   time.Duration
	tentativas  int
	dormir      func(ctx context.Context, d time.Duration) error
	agora       func() time.Time
	ultimoEnvio time.Time
}

type Opcao func(*Cliente)

// ComURLBase troca o endereço da API. Usado nos testes.
func ComURLBase(url string) Opcao { return func(c *Cliente) { c.urlBase = url } }

// ComIntervalo define a pausa mínima entre dois envios.
func ComIntervalo(d time.Duration) Opcao { return func(c *Cliente) { c.intervalo = d } }

// ComTentativas define quantas vezes insistir diante de HTTP 429.
func ComTentativas(n int) Opcao { return func(c *Cliente) { c.tentativas = n } }

// ComRelogio troca a função de espera e a de hora atual. Usado nos testes.
func ComRelogio(dormir func(context.Context, time.Duration) error, agora func() time.Time) Opcao {
	return func(c *Cliente) {
		c.dormir = dormir
		c.agora = agora
		
	}
}

func NovoCliente(token, chatID string, opcoes ...Opcao) *Cliente {
	c := &Cliente{
		token:      token,
		chatID:     chatID,
		urlBase:    URLBasePadrao,
		http:       &http.Client{Timeout: 10 * time.Second},
		intervalo:  IntervaloPadrao,
		tentativas: TentativasPadrao,
		dormir:     esperar,
		agora:      time.Now,
	}
	for _, aplicar := range opcoes {
		aplicar(c)
	}
	return c
}

type pedidoSendMessage struct {
	ChatID    string `json:"chat_id"`
	Text      string `json:"text"`
	ParseMode string `json:"parse_mode"`
}

type respostaAPI struct {
	OK          bool   `json:"ok"`
	Description string `json:"description"`
	Parameters  struct {
		RetryAfter int `json:"retry_after"` // segundos, presente no HTTP 429
	} `json:"parameters"`
}

// Notificar implementa application.Notificador.
func (c *Cliente) Notificar(ctx context.Context, promocao domain.Promocao) error {
	corpo, err := json.Marshal(pedidoSendMessage{
		ChatID:    c.chatID,
		Text:      FormatarMensagem(promocao),
		ParseMode: "HTML",
	})
	if err != nil {
		return err
	}

	for tentativa := 1; ; tentativa++ {
		if err := c.respeitarIntervalo(ctx); err != nil {
			return err
		}

		status, resposta, err := c.enviar(ctx, corpo)
		c.ultimoEnvio = c.agora()
		if err != nil {
			return err
		}
		if resposta.OK {
			return nil
		}
		if status != http.StatusTooManyRequests || tentativa >= c.tentativas {
			return fmt.Errorf("telegram: HTTP %d: %s", status, resposta.Description)
		}

		espera := time.Duration(resposta.Parameters.RetryAfter) * time.Second
		if espera <= 0 {
			espera = c.intervalo
		}
		if err := c.dormir(ctx, espera); err != nil {
			return err
		}
	}
}

func (c *Cliente) respeitarIntervalo(ctx context.Context) error {
	if c.ultimoEnvio.IsZero() {
		return nil
	}
	decorrido := c.agora().Sub(c.ultimoEnvio)
	if decorrido >= c.intervalo {
		return nil
	}
	return c.dormir(ctx, c.intervalo-decorrido)
}

func (c *Cliente) enviar(ctx context.Context, corpo []byte) (int, respostaAPI, error) {
	url := fmt.Sprintf("%s/bot%s/sendMessage", c.urlBase, c.token)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(corpo))
	if err != nil {
		return 0, respostaAPI{}, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return 0, respostaAPI{}, fmt.Errorf("telegram: %w", err)
	}
	defer resp.Body.Close()

	var resultado respostaAPI
	if err := json.NewDecoder(resp.Body).Decode(&resultado); err != nil {
		return resp.StatusCode, respostaAPI{}, fmt.Errorf(
			"telegram: resposta inesperada (HTTP %d): %w", resp.StatusCode, err)
	}
	return resp.StatusCode, resultado, nil
}

// esperar dorme d, ou menos se o contexto for cancelado antes.
func esperar(ctx context.Context, d time.Duration) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(d):
		return nil
	}
}
