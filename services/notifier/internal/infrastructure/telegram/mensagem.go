package telegram

import (
	"fmt"
	"html"
	"strings"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/domain"
)

// FormatarMensagem monta o texto em HTML aceito pelo Telegram.
//
// Exemplo, com cupom de valor conhecido:
//
//	🔥 <b>Promoção na Kabum</b>
//	Fonte Gamer Rise Mode Elektra, 650W
//	De R$ 377,77 por <b>R$ 265,99</b> (29,59% de desconto)
//	🎟️ Cupom <code>ESQUENTA</code> (5,00% já aplicado no preço)
//	<a href="https://...">Ver na loja</a>
//
// Quando a loja não informa o valor do cupom, a linha vira
// "🎟️ Cupom <code>10DO10</code> na loja (desconto não informado)".
// Sem cupom, a linha não aparece.
func FormatarMensagem(p domain.Promocao) string {
	var b strings.Builder

	fmt.Fprintf(&b, "🔥 <b>Promoção na %s</b>\n", html.EscapeString(capitalizar(p.Loja)))
	b.WriteString(html.EscapeString(p.Titulo()))
	b.WriteString("\n")
	fmt.Fprintf(&b, "De %s por <b>%s</b> (%s%% de desconto)",
		formatarReal(p.PrecoReferencia),
		formatarReal(p.PrecoFinal),
		virgulaDecimal(p.DescontoPercentual),
	)
	if p.Cupom.Existe() {
		b.WriteString("\n")
		b.WriteString(linhaCupom(p.Cupom))
	}
	if p.URL != "" {
		fmt.Fprintf(&b, "\n<a href=\"%s\">Ver na loja</a>", html.EscapeString(p.URL))
	}

	return b.String()
}

func linhaCupom(c domain.Cupom) string {
	codigo := html.EscapeString(c.Codigo)
	if c.ValorConhecido() {
		return fmt.Sprintf("🎟️ Cupom <code>%s</code> (%s%% já aplicado no preço)", codigo, virgulaDecimal(c.DescontoPercentual))
	}
	return fmt.Sprintf("🎟️ Cupom <code>%s</code> na loja (desconto não informado)", codigo)
}

// formatarReal converte "1099.90" em "R$ 1.099,90".
func formatarReal(valor string) string {
	inteiro, decimal, _ := strings.Cut(valor, ".")
	if decimal == "" {
		decimal = "00"
	}
	return "R$ " + separarMilhares(inteiro) + "," + decimal
}

// virgulaDecimal troca o ponto por vírgula: "18.04" vira "18,04".
func virgulaDecimal(valor string) string {
	return strings.ReplaceAll(valor, ".", ",")
}

// separarMilhares converte "1099" em "1.099".
func separarMilhares(digitos string) string {
	if len(digitos) <= 3 {
		return digitos
	}
	var b strings.Builder
	primeiro := len(digitos) % 3
	if primeiro > 0 {
		b.WriteString(digitos[:primeiro])
	}
	for i := primeiro; i < len(digitos); i += 3 {
		if b.Len() > 0 {
			b.WriteString(".")
		}
		b.WriteString(digitos[i : i+3])
	}
	return b.String()
}

func capitalizar(texto string) string {
	if texto == "" {
		return texto
	}
	return strings.ToUpper(texto[:1]) + texto[1:]
}
