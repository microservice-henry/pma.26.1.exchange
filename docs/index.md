# Exchange API

Documentação do projeto desenvolvido para a disciplina de Projeto de Microsserviços e APIs (PMA 26.1).

---

## Integrantes

| Nome | GitHub |
|---|---|
| Henry Idesis |
| Nathan Benaion |
| Kauã Makiyama |

---

## Sobre o Projeto

A **Exchange API** é um microsserviço desenvolvido em Python com FastAPI que permite a conversão de taxas de câmbio entre moedas. O serviço consome a [AwesomeAPI](https://docs.awesomeapi.com.br/) como provedor externo de cotações e exige autenticação via JWT para acesso aos endpoints.

---

## Repositórios

| Serviço | Repositório |
|---|---|
| Exchange API | <!-- link do repositório --> |
| <!-- outro serviço --> | <!-- link --> |

---

## Apresentação em Vídeo

<!-- Adicionar link do vídeo de apresentação (2-3 minutos) aqui -->

> Vídeo de apresentação disponível em: [link do vídeo]()

---

## Arquitetura

O microsserviço de exchange faz parte de uma arquitetura maior composta pelos seguintes serviços:

- **gateway** — ponto de entrada das requisições
- **auth** — autenticação e geração de tokens JWT
- **account** — gerenciamento de contas
- **product** — gerenciamento de produtos
- **order** — gerenciamento de pedidos
- **exchange** — conversão de câmbio (este serviço)

O exchange **não** está dentro da camada confiável (Trusted Layer) e se comunica com uma API de terceiros para obter as cotações.
