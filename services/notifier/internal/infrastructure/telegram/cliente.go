// Package telegram envia mensagens pela Bot API usando só net/http.
//
// Um único endpoint nos interessa, sendMessage, então não vale uma
// biblioteca. A URL base é configurável para os testes apontarem para um
// servidor falso.
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

const URLBasePadrao = "https://api.telegram.org"

type Cliente struct {
	token   string
	chatID  string
	urlBase string
	http    *http.Client
}

type Opcao func(*Cliente)

// ComURLBase troca o endereço da API. Usado nos testes.
func ComURLBase(url string) Opcao {
	return func(c *Cliente) { c.urlBase = url }
}

func NovoCliente(token, chatID string, opcoes ...Opcao) *Cliente {
	c := &Cliente{
		token:   token,
		chatID:  chatID,
		urlBase: URLBasePadrao,
		http:    &http.Client{Timeout: 10 * time.Second},
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

	url := fmt.Sprintf("%s/bot%s/sendMessage", c.urlBase, c.token)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(corpo))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("telegram: %w", err)
	}
	defer resp.Body.Close()

	var resultado respostaAPI
	if err := json.NewDecoder(resp.Body).Decode(&resultado); err != nil {
		return fmt.Errorf("telegram: resposta inesperada (HTTP %d): %w", resp.StatusCode, err)
	}
	if !resultado.OK {
		return fmt.Errorf("telegram: HTTP %d: %s", resp.StatusCode, resultado.Description)
	}
	return nil
}
