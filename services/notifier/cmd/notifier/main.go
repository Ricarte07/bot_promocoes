// Ponto de entrada do notifier: lê promoções do Redis e manda ao Telegram.
//
// Uso, dentro de services/notifier:
//
//	go run ./cmd/notifier            # consome o stream até receber Ctrl+C
//	go run ./cmd/notifier -testar    # manda uma mensagem de teste e sai
//
// Configuração por variáveis de ambiente (ou pelo .env na raiz do projeto):
//
//	TELEGRAM_BOT_TOKEN            token dado pelo @BotFather
//	TELEGRAM_CHAT_ID              chat, grupo ou canal que recebe as mensagens
//	TELEGRAM_INTERVALO_SEGUNDOS   pausa mínima entre mensagens; padrão 1.1
//	REDIS_URL                     padrão redis://localhost:6379/0
package main

import (
	"bufio"
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/application"
	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
	"github.com/Ricarte07/bot_promocoes/notifier/internal/infrastructure/queue"
	"github.com/Ricarte07/bot_promocoes/notifier/internal/infrastructure/telegram"
)

type config struct {
	tokenTelegram  string
	chatID         string
	redisURL       string
	intervaloEnvio time.Duration
}

func main() {
	arquivoEnv := flag.String("env", "../../.env", "arquivo .env a carregar, se existir")
	testar := flag.Bool("testar", false, "envia uma mensagem de teste ao Telegram e sai")
	flag.Parse()

	log := slog.New(slog.NewTextHandler(os.Stderr, nil))

	if err := carregarDotEnv(*arquivoEnv); err != nil {
		log.Warn("não li o .env", "arquivo", *arquivoEnv, "erro", err)
	}
	cfg, err := carregarConfig()
	if err != nil {
		log.Error("configuração inválida", "erro", err)
		os.Exit(2)
	}

	ctx, parar := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer parar()

	notificador := telegram.NovoCliente(
		cfg.tokenTelegram, cfg.chatID, telegram.ComIntervalo(cfg.intervaloEnvio),
	)
	log.Info("intervalo entre mensagens", "segundos", cfg.intervaloEnvio.Seconds())

	if *testar {
		if err := enviarTeste(ctx, notificador); err != nil {
			log.Error("teste falhou", "erro", err)
			os.Exit(1)
		}
		log.Info("mensagem de teste enviada; confira o Telegram")
		return
	}

	cliente, err := conectarRedis(ctx, cfg.redisURL)
	if err != nil {
		log.Error("não conectei ao Redis", "url", cfg.redisURL, "erro", err)
		os.Exit(1)
	}
	defer cliente.Close()

	casoDeUso := application.NovoNotificarPromocao(notificador)
	fonte := queue.NovoConsumidor(cliente, log)

	err = fonte.Executar(ctx, casoDeUso.Executar)
	if err != nil && !errors.Is(err, context.Canceled) {
		log.Error("consumidor parou", "erro", err)
		os.Exit(1)
	}
	log.Info("notifier encerrado")
}

func carregarConfig() (config, error) {
	cfg := config{
		tokenTelegram: os.Getenv("TELEGRAM_BOT_TOKEN"),
		chatID:        os.Getenv("TELEGRAM_CHAT_ID"),
		redisURL:      os.Getenv("REDIS_URL"),
	}
	if cfg.redisURL == "" {
		cfg.redisURL = "redis://localhost:6379/0"
	}
	if cfg.tokenTelegram == "" || strings.HasPrefix(cfg.tokenTelegram, "coloque_") {
		return cfg, errors.New("defina TELEGRAM_BOT_TOKEN")
	}
	if cfg.chatID == "" || strings.HasPrefix(cfg.chatID, "coloque_") {
		return cfg, errors.New("defina TELEGRAM_CHAT_ID")
	}
	intervalo, err := lerIntervalo(os.Getenv("TELEGRAM_INTERVALO_SEGUNDOS"))
	if err != nil {
		return cfg, fmt.Errorf("TELEGRAM_INTERVALO_SEGUNDOS: %w", err)
	}
	cfg.intervaloEnvio = intervalo
	return cfg, nil
}

// lerIntervalo converte o texto da variável em duração. Vazio usa o padrão do
// cliente Telegram; aceita decimais com ponto ou vírgula, como "1.1" ou "90".
func lerIntervalo(valor string) (time.Duration, error) {
	valor = strings.TrimSpace(strings.ReplaceAll(valor, ",", "."))
	if valor == "" {
		return telegram.IntervaloPadrao, nil
	}
	segundos, err := strconv.ParseFloat(valor, 64)
	if err != nil {
		return 0, fmt.Errorf("%q não é um número de segundos", valor)
	}
	if segundos <= 0 {
		return 0, errors.New("precisa ser maior que zero")
	}
	return time.Duration(segundos * float64(time.Second)), nil
}

func conectarRedis(ctx context.Context, url string) (*redis.Client, error) {
	opcoes, err := redis.ParseURL(url)
	if err != nil {
		return nil, err
	}
	cliente := redis.NewClient(opcoes)
	if err := cliente.Ping(ctx).Err(); err != nil {
		_ = cliente.Close()
		return nil, err
	}
	return cliente, nil
}

func enviarTeste(ctx context.Context, notificador application.Notificador) error {
	return notificador.Notificar(ctx, domain.Promocao{
		ProdutoID:          "teste",
		Loja:               "notifier",
		Nome:               "Mensagem de teste: o notifier está conectado ao Telegram",
		PrecoAtual:         "80.00",
		PrecoFinal:         "80.00",
		PrecoReferencia:    "100.00",
		DescontoPercentual: "20.00",
		OcorridoEm:         time.Now(),
	})
}

// carregarDotEnv lê linhas CHAVE=VALOR e define só as variáveis ainda não definidas.
// Arquivo inexistente não é erro: em produção a configuração vem do ambiente.
func carregarDotEnv(caminho string) error {
	arquivo, err := os.Open(caminho)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	defer arquivo.Close()

	leitor := bufio.NewScanner(arquivo)
	for leitor.Scan() {
		linha := strings.TrimSpace(leitor.Text())
		if linha == "" || strings.HasPrefix(linha, "#") {
			continue
		}
		chave, valor, ok := strings.Cut(linha, "=")
		if !ok {
			return fmt.Errorf("linha sem '=': %q", linha)
		}
		chave, valor = strings.TrimSpace(chave), strings.Trim(strings.TrimSpace(valor), `"'`)
		if os.Getenv(chave) == "" {
			os.Setenv(chave, valor)
		}
	}
	return leitor.Err()
}
