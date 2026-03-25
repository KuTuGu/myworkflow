---
name: pdf-translate
description: Use PDFMathTranslate (pdf2zh) to translate PDF documents while preserving layouts, 
formulas, charts, and tables. Supports multiple translation services including 
LLM-based services like OpenAI, Ollama, DeepSeek, etc.
---

Scientific PDF document translation preserving layouts.


## Install

1. Python installed (3.11 <= version <= 3.12)
2. Install our package:

   ```bash
   pip install uv
   uv tool install --python 3.12 pdf2zh
   ```

3. Execute translation:

   ```bash
   pdf2zh document.pdf
   ```

## Advanced options

In the following table, we list all advanced options for reference:

| Option                | Function                                                                                                      | Example                                        |
| --------------------- | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| files                 | Local files                                                                                                   | `pdf2zh ~/local.pdf`                           |
| links                 | Online files                                                                                                  | `pdf2zh http://arxiv.org/paper.pdf`            |
| `-i`                  | [Enter GUI](#gui)                                                                                             | `pdf2zh -i`                                    |
| `-p`                  | [Partial document translation](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#partial) | `pdf2zh example.pdf -p 1`                      |
| `-li`                 | [Source language](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#languages)            | `pdf2zh example.pdf -li en`                    |
| `-lo`                 | [Target language](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#languages)            | `pdf2zh example.pdf -lo zh`                    |
| `-s`                  | [Translation service](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#services)         | `pdf2zh example.pdf -s deepl`                  |
| `-t`                  | [Multi-threads](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#threads)                | `pdf2zh example.pdf -t 1`                      |
| `-o`                  | Output dir                                                                                                    | `pdf2zh example.pdf -o output`                 |
| `-f`, `-c`            | [Exceptions](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#exceptions)                | `pdf2zh example.pdf -f "(MS.*)"`               |
| `-cp`                 | Compatibility Mode                                                                                            | `pdf2zh example.pdf --compatible`              |
| `--skip-subset-fonts` | [Skip font subset](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#font-subset)         | `pdf2zh example.pdf --skip-subset-fonts`       |
| `--ignore-cache`      | [Ignore translate cache](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#cache)         | `pdf2zh example.pdf --ignore-cache`            |
| `--share`             | Public link                                                                                                   | `pdf2zh -i --share`                            |
| `--authorized`        | [Authorization](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#auth)                   | `pdf2zh -i --authorized users.txt [auth.html]` |
| `--prompt`            | [Custom Prompt](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#prompt)                 | `pdf2zh --prompt [prompt.txt]`                 |
| `--onnx`              | [Use Custom DocLayout-YOLO ONNX model]                                                                        | `pdf2zh --onnx [onnx/model/path]`              |
| `--serverport`        | [Use Custom WebUI port]                                                                                       | `pdf2zh --serverport 7860`                     |
| `--dir`               | [batch translate]                                                                                             | `pdf2zh --dir /path/to/translate/`             |
| `--config`            | [configuration file](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#cofig)             | `pdf2zh --config /path/to/config/config.json`  |
| `--serverport`        | [custom gradio server port]                                                                                   | `pdf2zh --serverport 7860`                     |
| `--mode`              | Translation mode: `fast` (default, v1) or `precise` (v2, experimental, requires pdf2zh_next submodule)         | `pdf2zh --mode precise example.pdf`            |
| `--babeldoc`          | Use Experimental backend [BabelDOC](https://funstory-ai.github.io/BabelDOC/) to translate                     | `pdf2zh --babeldoc` -s openai example.pdf      |
| `--mcp`               | Enable MCP STDIO mode                                                                                         | `pdf2zh --mcp`                                 |
| `--sse`               | Enable MCP SSE mode                                                                                           | `pdf2zh --mcp --sse`                           |

For detailed explanations, please refer to our document about [Advanced Usage](./references/ADVANCED.md) for a full list of each option.
