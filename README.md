# Monitor de Aluguéis → Telegram

Todo dia às 08:00 este robô procura **imóveis de 1 quarto (casa ou apartamento) para
aluguel anual em Gramado e Canela** e te manda no Telegram **só os anúncios novos** e
os que **baixaram de preço**. Roda de graça na nuvem (GitHub Actions).

**Fontes:**
- Portais: ZAP Imóveis, Viva Real, Chaves na Mão e Wimoveis (grupo Imovelweb)
- Imobiliárias locais: Altreiter Imóveis, Bordin Imóveis e Gramado Garden

Cada imóvel chega como uma **foto com a descrição na legenda**. Só a primeira mensagem do
dia (o resumo) faz o celular tocar; as dos imóveis chegam em silêncio. Para receber uma
lista compacta, só com texto, use `fotos = false` no `config.toml`.

O mesmo imóvel anunciado em mais de um site aparece uma vez só, com os links de todos.
Aluguel por temporada e imóveis comerciais são descartados.

> **Ficaram de fora:** Imovelweb, OLX, Mercado Livre, Trovit, Mitula e Nestoria
> bloqueiam acesso automatizado. Facebook Marketplace exige login e proíbe coleta
> automática; para ele, use **Salvar pesquisa** no próprio app do Facebook. O
> QuintoAndar não atua na região. Realiza Imóveis, Gramado Administradora e In Out
> não têm listagem pública que dê para ler.

---

## Configuração (igual ao monitor de carros)

### 1. Criar um bot novo no Telegram
1. No **@BotFather**, mande `/newbot` e crie o bot (ex.: "Aluguel Gramado").
2. Guarde o **token**.
3. Mande um "oi" para o bot novo.
4. Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` e anote o `"chat":{"id":...}`.
   Esse é o **CHAT_ID**. Costuma ser o mesmo número do bot de carros, porque é o seu perfil.

### 2. Repositório novo no GitHub
Crie um repositório (ex.: `monitor-imoveis`) e, **nesta pasta**, rode:
```bash
git init
git add .
git commit -m "Monitor de aluguéis"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/monitor-imoveis.git
git push -u origin main
```

### 3. Segredos
Em **Settings → Secrets and variables → Actions**, crie `TELEGRAM_TOKEN` (o token do bot
**novo**) e `TELEGRAM_CHAT_ID`.

### 4. Testar
**Actions → Monitor de aluguéis diário → Run workflow**. A mensagem chega em ~3 minutos.

---

## Como mudar a busca
Edite o [config.toml](config.toml):
- `cidades`: ex. `["Gramado", "Canela", "Nova Petrópolis"]`
- `quartos_min` / `quartos_max`: ex. 1 e 2 para aceitar 1 ou 2 quartos
- `preco_min` / `preco_max`: faixa do aluguel (0 = sem limite)
- `palavras_excluir` / `tipos_excluir`: descartes
- `[fontes.imobiliarias].sites`: dá para acrescentar outras imobiliárias que usem o
  mesmo tipo de site (com a página `/alugar-imoveis`)

## Rodar no seu PC (opcional)
```bash
pip install -r requirements.txt
python main.py --teste
```

## Se algo quebrar
Quando uma fonte falha, a mensagem do dia avisa ("⚠️ Fontes com problema hoje"), e as
demais continuam. O código de cada site fica em `fontes/`.
