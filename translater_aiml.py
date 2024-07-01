import os
import xml.etree.ElementTree as ET
from googletrans import Translator
import re
import tempfile
import time
import unicodedata

LOG_FILE = 'translation_progress.log'
TRANSLATED_TEXT_FILE = 'translated_text.log'

def load_translation_progress():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            translated_elements = set(line.strip() for line in f)
        return translated_elements
    return set()

def save_translation_progress(element_id):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(element_id + '\n')

def save_translated_text(element_id, text):
    with open(TRANSLATED_TEXT_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{element_id}\t{text}\n")

def load_translated_text():
    if os.path.exists(TRANSLATED_TEXT_FILE):
        translated_texts = {}
        with open(TRANSLATED_TEXT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                element_id, text = line.strip().split('\t', 1)
                translated_texts[element_id] = text
        return translated_texts
    return {}

def clean_xml_file(input_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    cleaned_lines = []
    inside_root = False
    for line in lines:
        if '<aiml' in line:
            inside_root = True
        if inside_root and line.strip():  # Only add non-empty lines
            cleaned_lines.append(line.strip())
        if '</aiml>' in line:
            break

    cleaned_content = ''.join(cleaned_lines)  # No newline between lines

    cleaned_file = input_file + '.cleaned'
    with open(cleaned_file, 'w', encoding='utf-8') as file:
        file.write(cleaned_content)

    return cleaned_file

def validate_xml_file(file_path):
    try:
        tree = ET.parse(file_path)
        return True
    except ET.ParseError as e:
        print(f"Erro de análise no arquivo {file_path}: {e}")
        return False

def get_element_identifier(element, parent_map):
    parts = []
    while element is not None:
        parent = parent_map.get(element)
        if parent is not None:
            index = list(parent).index(element)
            parts.append(f"{element.tag}[{index}]")
        else:
            parts.append(element.tag)
        element = parent
    parts.reverse()
    return '/'.join(parts)

def protect_code_snippets(text):
    code_snippets = re.findall(r'<[^>]+>', text)
    for i, snippet in enumerate(code_snippets):
        text = text.replace(snippet, f"__CODE_SNIPPET_{i}__", 1)
    return text, code_snippets

def restore_code_snippets(text, code_snippets):
    for i, snippet in enumerate(code_snippets):
        text = text.replace(f"__CODE_SNIPPET_{i}__", snippet, 1)
    return text

def normalize_text(text):
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')

def translate_and_format_text(element, translator):
    if element.text is None or not element.text.strip():
        return element.text
    text = element.text.strip()
    protected_text, code_snippets = protect_code_snippets(text)
    translated = translator.translate(protected_text, src='en', dest='pt').text
    translated = restore_code_snippets(translated, code_snippets)
    if element.tag.lower() == 'pattern':
        translated = translated.upper()
        translated = normalize_text(translated)
    return translated

def retry_translation(translator, text, src, dest, retries=3, delay=5):
    if not text or text.strip() == "":
        return text
    for attempt in range(retries):
        try:
            result = translator.translate(text, src=src, dest=dest)
            if result is None or result.text is None:
                raise Exception("Received None from translator")
            return result.text
        except Exception as e:
            print(f"Erro ao traduzir o texto '{text}': {e}")
            if attempt < retries - 1:
                print(f"Tentando novamente em {delay} segundos...")
                time.sleep(delay)
            else:
                raise

def translate_aiml_file(input_file, output_file, target_language='pt'):
    try:
        cleaned_file = clean_xml_file(input_file)
        if not validate_xml_file(cleaned_file):
            print("Erro na validação do arquivo XML após limpeza.")
            return

        translator = Translator()
        tree = ET.parse(cleaned_file)
        root = tree.getroot()
        parent_map = {c: p for p in tree.iter() for c in p}

        translated_elements = load_translation_progress()
        translated_texts = load_translated_text()

        count = len(translated_elements)

        try:
            for element in root.iter():
                if element.text is not None and element.text.strip():
                    element_id = get_element_identifier(element, parent_map)
                    if element_id not in translated_elements:
                        try:
                            if element_id in translated_texts:
                                element.text = translated_texts[element_id]
                            else:
                                print(f"Traduzindo texto: '{element.text}'")
                                translated_text = retry_translation(translator, element.text.strip(), 'en', 'pt')
                                if element.tag.lower() == 'pattern':
                                    translated_text = translated_text.upper()
                                    translated_text = normalize_text(translated_text)
                                save_translated_text(element_id, translated_text)
                                element.text = translated_text
                            save_translation_progress(element_id)
                            count += 1
                            print(f"'{element.text}' Contagem da linha: {count}")
                        except Exception as e:
                            print(f"Erro ao traduzir o texto '{element.text}': {e}")
                            element.text = element.text
                # Handle tail text (text after an element)
                if element.tail is not None and element.tail.strip():
                    tail_id = get_element_identifier(element, parent_map) + "_tail"
                    if tail_id not in translated_elements:
                        try:
                            if tail_id in translated_texts:
                                element.tail = translated_texts[tail_id]
                            else:
                                print(f"Traduzindo texto adjacente: '{element.tail}'")
                                translated_tail = retry_translation(translator, element.tail.strip(), 'en', 'pt')
                                save_translated_text(tail_id, translated_tail)
                                element.tail = translated_tail
                            save_translation_progress(tail_id)
                            count += 1
                            print(f"'{element.tail}' Contagem da linha: {count}")
                        except Exception as e:
                            print(f"Erro ao traduzir o texto adjacente '{element.tail}': {e}")
                            element.tail = element.tail

            temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8')
            tree.write(temp_file.name, encoding='utf-8', xml_declaration=True)

            with open(temp_file.name, 'r', encoding='utf-8') as temp_f:
                content = temp_f.read()

            # Adjust content for necessary line breaks between tags
            content = content.strip('[]').replace('><', '>\n<')

            with open(output_file, 'w', encoding='utf-8') as out_f:
                out_f.write(content)

            os.remove(temp_file.name)
            print("Tradução concluída e salva com sucesso.")
        except KeyboardInterrupt:
            print("Tradução interrompida pelo usuário.")
    except Exception as e:
        print(f"Erro durante o processo de tradução: {e}")

if __name__ == "__main__":
    input_file = "/sdcard/Download/aiml-en-us-foundation-alice/mp0.aiml"
    output_file = "/sdcard/Download/aiml-en-us-foundation-alice/Alice/mp0.aiml"
    translate_aiml_file(input_file, output_file)