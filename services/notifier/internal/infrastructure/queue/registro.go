package queue

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"
)

// PrefixoEnviados separa no Redis as chaves de "já enviado" das demais.
const PrefixoEnviados = "enviado:"

// RegistroRedis implementa application.RegistroDeEnvios: cada promoção
// enviada vira uma chave com prazo de validade, que o próprio Redis apaga
// quando vence.
type RegistroRedis struct {
	cliente *redis.Client
}

func NovoRegistroRedis(cliente *redis.Client) *RegistroRedis {
	return &RegistroRedis{cliente: cliente}
}

func (r *RegistroRedis) JaEnviado(ctx context.Context, chave string) (bool, error) {
	existe, err := r.cliente.Exists(ctx, PrefixoEnviados+chave).Result()
	return existe > 0, err
}

func (r *RegistroRedis) MarcarEnviado(ctx context.Context, chave string, validade time.Duration) error {
	return r.cliente.Set(ctx, PrefixoEnviados+chave, time.Now().UTC().Format(time.RFC3339), validade).Err()
}
