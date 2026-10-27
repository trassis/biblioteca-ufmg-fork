# Plano: otimizar a geração dos hashes

## Objetivo

Reduzir o tempo de geração da biblioteca sem alterar os hashes existentes, os códigos dos algoritmos ou o guia `theoretical/`.

## 1. Medir o fluxo atual

- [x] Medir separadamente compilação C++, geração e compilação Typst.
- [x] Registrar quantidade de hashes e processos iniciados pelo gerador.
- [x] Salvar referências dos modos padrão e `--printall` e comparar a saída completa byte a byte.
- [x] Automatizar medições repetidas com cache frio, cache quente, geração paralela e alteração de um algoritmo.

Implementação: `typst/benchmark.py` e `--stats`. Resultados e metodologia: `typst/BENCHMARK.md`.

## 2. Ler cada arquivo uma única vez

- [x] Carregar conteúdo e linhas em memória.
- [x] Reutilizar as linhas para títulos, flags, listagens e trechos de hash.
- [x] Selecionar trechos por índices, sem reabrir o arquivo a cada hash.
- [x] Preservar a seleção anterior de blocos por chaves e o tratamento especial de `vimrc`.

## 3. Implementar cache por arquivo

- [x] Armazenar a listagem com os hashes, indexada pelo conteúdo completo do arquivo e sua configuração.
- [x] Incluir versão de algoritmo/formato, tamanho dos hashes, identidade/opções do pré-processador e ambiente relevante na chave.
- [x] Reutilizar somente entradas compatíveis e invalidar apenas arquivos alterados.
- [x] Desconsiderar arquivos removidos, sem usá-los na geração.
- [x] Gravar por substituição atômica e validar checksum ao ler.
- [x] Recalcular entradas ausentes ou corrompidas e continuar sem cache caso o diretório esteja indisponível.
- [x] Oferecer `--no-cache`, `--rebuild-cache` e `--cache-dir`.
- [x] Ignorar o cache no Git e documentar sua limpeza.

Entradas antigas são removidas manualmente; não há coleta automática. Listagens que produzem diagnósticos não são armazenadas, para não ocultar avisos nas execuções seguintes.

## 4. Eliminar o arquivo temporário de cada hash

- [x] Enviar o trecho ao pré-processador pela entrada padrão.
- [x] Capturar stdout e stderr e verificar o código de saída.
- [x] Alimentar stdin e drenar ambas as saídas simultaneamente com pipes não bloqueantes e `poll`.
- [x] Tratar falhas de comunicação sem aceitar resultados parciais nem deixar processos sem coleta.
- [x] Manter os comandos GCC e Clang anteriores, ambos já operando sobre stdin.

Decisão de compatibilidade: o cache persistente é desativado quando o gerador é compilado com Clang. O pré-processamento completo do Clang pode depender de includes e macros de tempo, ainda não rastreados. O ambiente disponível não tem Clang; a validação integral dos hashes foi feita com GCC 12.2.

## 5. Reduzir subprocessos

- [x] Aplicar em C++ o limite de 10 mil linhas por trecho e a remoção de linhas `#w`, na ordem original.
- [x] Manter um pré-processador externo por hash não armazenado em cache.
- [x] Remover os mesmos espaços em branco, inclusive dentro de strings.
- [x] Calcular MD5 e truncar o hexadecimal em C++, sem nova dependência externa.
- [x] Comparar o resultado com o pipeline anterior e com vetores MD5 conhecidos.

Implementação: `typst/hash_support.hpp`. O comportamento dos comentários continua sendo definido pelo pré-processador; não foi substituído por expressões regulares nem por um único processamento do arquivo inteiro.

## 6. Avaliar paralelismo

- [x] Medir execução serial e com quatro trabalhadores.
- [x] Implementar `--jobs N`, limitado a 1–64 trabalhadores por arquivo.
- [x] Evitar temporários compartilhados e permitir acesso concorrente seguro ao cache por gravações atômicas.
- [x] Emitir o documento na ordem anterior, independentemente da conclusão das tarefas.
- [x] Manter uma única camada de paralelismo.

Decisão: padrão de um trabalhador. Quatro trabalhadores não melhoraram o tempo no ambiente medido; a opção permanece disponível para outras máquinas.

## 7. Testes e critérios de aceite

- [x] Saídas padrão e `--printall` idênticas às referências anteriores.
- [x] Cobertura de comentários, macros, `#warning`, strings com espaços, tabs, acentos, linhas vazias, chaves e trechos maiores que 10 mil linhas.
- [x] Cobertura de cache hit, alteração/remoção de arquivo, mudança de configuração/identidade do pré-processador e cache corrompido.
- [x] Cobertura de geração sem cache e de falhas do pré-processador.
- [x] Cobertura de pipes maiores que seus buffers, encerramento antecipado e dois geradores compartilhando o cache.
- [x] Compilação Typst validada sem modificar os PDFs versionados.
- [x] Ganhos de tempo registrados para geração completa, sem alterações e após alterar um algoritmo.
- [x] Atualizar `README.md`, `pdf/README.md` e `.gitignore`.

## Limites mantidos

Não houve mudança do algoritmo de hash, de suas limitações semânticas ou dos arquivos em `Codigo/` e `theoretical/`. O tratamento de erros ficou mais estrito: uma falha do pré-processador agora interrompe a geração, em vez de produzir um hash de saída parcial.
