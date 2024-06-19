#!/usr/bin/python3
import os
import xml.etree.ElementTree as ET
from googletrans import Translator
from langdetect import detect, LangDetectException
import tempfile
import shutil

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
        if inside_root:
            cleaned_lines.append(line.strip())
        if '</aiml>' in line:
            cleaned_lines.append('\n')
            break

    cleaned_content = '\n'.join(cleaned_lines)
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

def translate_and_format_text(element, target_language, translator):

    detected_lang = detect(element.text)
    if detected_lang != target_language:
        translated = translator.translate(element.text, dest=target_language).text
        if element.tag.lower() == 'pattern':
            translated = translated.upper()
        return translated
    return element.text

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
                if element.text and element.text.strip():
                    element_id = get_element_identifier(element, parent_map)
                    if element_id not in translated_elements:
                        try:
                            if element_id in translated_texts:
                                element.text = translated_texts[element_id]
                            else:
                                translated_text = translate_and_format_text(element, target_language, translator)
                                element.text = translated_text
                                save_translated_text(element_id, translated_text)
                            save_translation_progress(element_id)
                            count += 1
                            print(element.text, "Contagem da linha: {}".format(count))
                        except LangDetectException:
                            print(f"Não foi possível detectar o idioma do texto '{element.text}'")
                        except Exception as e:
                            print(f"Erro ao traduzir o texto '{element.text}': {e}")
                            element.text = element.text


            temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.xml')
            tree.write(temp_file.name, encoding='utf-8', xml_declaration=True)
            temp_file.close()


            with open(temp_file.name, 'r', encoding='utf-8') as temp_f:
                content = temp_f.read().lstrip()

            with open(output_file, 'w', encoding='utf-8') as out_f:
                out_f.write(content + '\n')

            print("Tradução concluída e salva com sucesso.")

        except Exception as e:
            print(f"Erro durante o processo de tradução: {e}")

    except KeyboardInterrupt:
        print("Tradução interrompida pelo usuário.")


input_file = '/sdcard/Download/aiml-en-us-foundation-alice/mp0.aiml'
output_file = '/sdcard/Download/aiml-en-us-foundation-alice/Alice/mp0.aiml'


translate_aiml_file(input_file, output_file)