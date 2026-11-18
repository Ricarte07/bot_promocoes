package application

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"
)

type registroFalso struct {
	enviados     map[string]time.Duration
	erroConsulta error
	erroMarcar   error
}

func novoRegistroFalso() *registroFalso {
	return &registroFalso{enviados: map[string]time.Duration{}}
}

func (r *registroFalso) JaEnviado(_ context.Context, chave string) (bool, error) {
	if r.erroConsulta != nil {
		return false, r.erroConsulta
	}
	_, ok := r.enviados[chave]
	return ok, nil
}

func (r *registroFalso) MarcarEnviado(_ context.Context, chave string, validade time.Duration) error {
	if r.erroMarcar != nil {
		return r.erroMarcar
	}
	r.enviados[chave] = validade
	return nil
}

func idempotente(proximo Notificador, registro RegistroDeEnvios) *NotificadorIdempotente {
	return NovoNotificadorIdempotente(proximo, registro, ValidadePadraoIdempotencia,
		slog.New(slog.NewTextHandler(io.Discard, nil)))
}

func TestPrimeiraVezEnviaEMarcaPorSeteDias(t *testing.T) {
	telegram, registro := &notificadorFalso{}, novoRegistroFalso()
	p := promocaoValida()

	if err := idempotente(telegram, registro).Notificar(context.Background(), p); err != nil {
		t.Fatalf("erro inesperado: %v", err)
	}

	if len(telegram.recebidas) != 1 {
		t.Fatalf("deveria enviar uma vez, enviou %d", len(telegram.recebidas))
	}
	if validade := registro.enviados[p.ChaveIdempotencia()]; validade != 7*24*time.Hour {
		t.Errorf("deveria marcar por 7 dias, marcou por %v", validade)
	}
}

func TestMesmaPromocaoRepetidaNaoEEnviadaDeNovo(t *testing.T) {
	telegram, registro := &notificadorFalso{}, novoRegistroFalso()
	decorado := idempotente(telegram, registro)
	p := promocaoValida()

	for range 3 {
		if err := decorado.Notificar(context.Background(), p); err != nil {
			t.Fatalf("erro inesperado: %v", err)
		}
	}

	if len(telegram.recebidas) != 1 {
		t.Errorf("três eventos iguais deveriam gerar 1 mensagem, geraram %d", len(telegram.recebidas))
	}
}

func TestPrecoMenorEAnunciadoDeNovo(t *testing.T) {
	telegram, registro := &notificadorFalso{}, novoRegistroFalso()
	decorado := idempotente(telegram, registro)
	p := promocaoValida()
	_ = decorado.Notificar(context.Background(), p)

	p.PrecoFinal = "850.00"
	_ = decorado.Notificar(context.Background(), p)

	if len(telegram.recebidas) != 2 {
		t.Errorf("uma queda de preço é outra promoção e deveria ser enviada, foram %d", len(telegram.recebidas))
	}
}

func TestFalhaNoEnvioNaoMarcaEDevolveErro(t *testing.T) {
	telegram, registro := &notificadorFalso{erro: errors.New("telegram fora")}, novoRegistroFalso()

	err := idempotente(telegram, registro).Notificar(context.Background(), promocaoValida())

	if err == nil {
		t.Fatal("o erro do envio deveria subir para a mensagem ficar pendente")
	}
	if len(registro.enviados) != 0 {
		t.Error("o que não saiu não pode ser marcado como enviado")
	}
}

func TestSemConseguirConsultarNaoEnvia(t *testing.T) {
	telegram, registro := &notificadorFalso{}, novoRegistroFalso()
	registro.erroConsulta = errors.New("redis fora")

	err := idempotente(telegram, registro).Notificar(context.Background(), promocaoValida())

	if err == nil || len(telegram.recebidas) != 0 {
		t.Errorf("sem saber se já foi enviada, não deveria enviar (erro=%v, enviadas=%d)", err, len(telegram.recebidas))
	}
}

func TestFalhaAoMarcarDepoisDeEnviarNaoDevolveErro(t *testing.T) {
	telegram, registro := &notificadorFalso{}, novoRegistroFalso()
	registro.erroMarcar = errors.New("redis caiu depois do envio")

	err := idempotente(telegram, registro).Notificar(context.Background(), promocaoValida())

	if err != nil {
		t.Errorf("a mensagem já saiu; devolver erro faria ela ser reenviada: %v", err)
	}
}
