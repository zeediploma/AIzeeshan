import streamlit as st
from gen import read_docx, audio_transcript, split_pdf_to_chunks, read_document, translate_and_combine_text, convert_text_to_docx_bytes
import io
from docx import Document
import time
import re
import json 
import os
st.title('Document Processor and Translator')

def read_word_pairs(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            word_pairs = json.load(file)
    else:
        word_pairs = []
    return word_pairs

def add_word_pair_to_file(file_path, original, translated):
    word_pairs = read_word_pairs(file_path)
    word_pairs.append({"original": original, "translated": translated})
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(word_pairs, file)

def word_pairs_interface(file_path='word_pairs.json'):
    if 'word_pairs' not in st.session_state:
        st.session_state.word_pairs = read_word_pairs(file_path)
    
    with st.expander("Manage Translation Word Pairs"):
        col1, col2 = st.columns(2)
        with col1:
            original_word = st.text_input("Original word:", key="original_word")
        with col2:
            translated_word = st.text_input("Translated version:", key="translated_word")
        
        if st.button("Add Word Pair"):
            add_word_pair_to_file(file_path, original_word, translated_word)
            st.session_state.word_pairs = read_word_pairs(file_path)  # Refresh the list
            st.success(f"Added word pair '{original_word}' -> '{translated_word}'")

        st.write("Current list of word pairs:")
        for pair in st.session_state.word_pairs:
            st.write(f"{pair['original']} -> {pair['translated']}")

def enhance_translation_prompt_with_word_pairs(prompt, word_pairs):
    if word_pairs:
        translations_instruction = "Translate the following words as specified: " + ", ".join([f"{pair['original']} as {pair['translated']}" for pair in word_pairs]) + "."
        enhanced_prompt = f"{prompt} {translations_instruction}"
    else:
        enhanced_prompt = prompt
    return enhanced_prompt


def save_last_state(data, filename="last_state.json"):
    """Saves the last transcription and translation to a file."""
    with open(filename, "w") as file:
        json.dump(data, file)

def load_last_state(filename="last_state.json"):
    """Loads the last transcription and translation from a file."""
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_custom_prompt(display_name, prompt_text):
    prompts = load_custom_prompts()  
    prompts[display_name] = prompt_text 
    with open("custom_prompts.json", "w") as file:
        json.dump(prompts, file)  

def load_custom_prompts():
    try:
        with open("custom_prompts.json", "r") as file:
            return json.load(file)  
    except (FileNotFoundError, json.JSONDecodeError):
        return {} 
    
def display_time_taken(process_name):
    """Function to display the time taken for a process in a human-readable format."""
    time_taken = st.session_state.get(f'{process_name}_time', None)
    if time_taken:
        if time_taken > 60:
            time_str = f"{time_taken / 60:.2f} minutes"
        else:
            time_str = f"{time_taken:.2f} seconds"
        st.info(f"{process_name.replace('_', ' ').capitalize()} completed in {time_str}.")

def transcription_download(text):
    doc = Document()
    doc.add_paragraph(text)
    doc_bytes = io.BytesIO()
    doc.save(doc_bytes)
    doc_bytes.seek(0)  
    return doc_bytes

saved_custom_prompts = load_custom_prompts()

file_types = {
    'MP3': ['mp3'],
    'DOC': ['docx'],
    'PDF': ['pdf']
}

if 'file_processed' not in st.session_state:
    st.session_state.file_processed = False
if 'transcript' not in st.session_state:
    st.session_state.transcript = ""
if 'translated_text' not in st.session_state:
    st.session_state.translated_text = ""
if 'source_language' not in st.session_state:
    st.session_state.source_language = ""
if 'target_language' not in st.session_state:
    st.session_state.target_language = ""
if 'translation_time' not in st.session_state:
    st.session_state.translation_time = ""
if 'transcription_time' not in st.session_state:
    st.session_state.transcription_time = ""



option = st.selectbox('Choose the type of file to upload', list(file_types.keys()))

file = st.file_uploader("Upload a file", type=file_types[option])

edited_text = ""

if file and (not hasattr(st.session_state, 'last_uploaded_file') or file != st.session_state.last_uploaded_file):
    st.session_state.file_processed = False
    st.session_state.transcript = ""
    st.session_state.translated_text = ""
    st.session_state.source_language = ""
    st.session_state.target_language = ""
    st.session_state.translation_time = ""
    st.session_state.transcription_time= ""
    st.session_state.last_uploaded_file = file

if file and not st.session_state.file_processed:
    if st.button('Transcribe'):
        st.session_state.transcript = ""

        start_time = time.time()
        if option == 'MP3':
            with st.spinner('Transcribing audio...'):
                st.session_state.transcript = audio_transcript(file)
                st.session_state.file_processed = True

        elif option == 'DOC':
            with st.spinner('Transcribing document...'):
                st.session_state.transcript = read_docx(file)
                st.session_state.file_processed = True

        elif option == 'PDF':
            temp_file_paths = split_pdf_to_chunks(file)
            extracted_texts = []

            for i, temp_file_path in enumerate(temp_file_paths, start=1):
                try:
                    
                    with st.spinner(f'Transcribing page to page {i*15}...'):
                        extracted_text = read_document(temp_file_path) 
                        extracted_texts.append(extracted_text)
                except Exception as e:
                    st.error(f"An error occurred while processing file {i}: {temp_file_path}. Error: {e}")
                    print(f"An error occurred while processing file {i}: {temp_file_path}. Error: {e}")
                    continue 

            st.session_state.transcript = "\n\n".join(extracted_texts)
            del extracted_text
            st.session_state.file_processed = True
        st.session_state['transcription_time'] = time.time() - start_time  
display_time_taken('transcription')
save_last_state({'transcript': st.session_state['transcript']})
if st.session_state.file_processed:          
    edited_text = st.text_area("Content (Edit as needed)", st.session_state.transcript, height=600)
    docx_bytes = transcription_download(st.session_state.transcript)
    st.download_button(
        label="Download Transcription",
        data=docx_bytes,
        file_name="transcription.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    source_language = st.text_input("Enter the source language:")
    target_language = st.text_input("Enter the target language:") 
    prompt_option = st.radio("Choose your prompt type", ["Use default prompt", "Enter custom prompt", "Use saved prompt"])

    if option == "MP3":
        timestamp_pattern = r"Start:\[\d{2}:\d{2}:\d{2}\] End:\[\d{2}:\d{2}:\d{2}\]\n"
        processed_transcript = re.sub(timestamp_pattern, '', edited_text)
        edited_text = processed_transcript

    word_pairs_interface()
    if prompt_option == "Enter custom prompt":
        display_name = st.text_input("Enter a name for your custom prompt:")
        custom_prompt = st.text_area("Enter your custom prompt:")
        if st.button("Save Custom Prompt"):
            save_custom_prompt(display_name, custom_prompt)
            st.success("Custom prompt saved.")
    elif prompt_option == "Use saved prompt":
        selected_name = st.selectbox("Select a saved prompt", list(saved_custom_prompts.keys()))
        custom_prompt = st.text_area("Edit your custom prompt:", value=saved_custom_prompts[selected_name])
        if st.button("Update Custom Prompt"):
            save_custom_prompt(selected_name, custom_prompt)
            st.success(f"Custom prompt '{selected_name}' updated.")

    if st.button('Translate'):
        start_time = time.time()
        word_pairs = read_word_pairs('word_pairs.json')
        if edited_text:
            with st.spinner(f'Translating to {target_language}...'):
                if prompt_option == "Use default prompt":
                    prompt = f"""You are a professional translator. You have to translate the provided text into {target_language}. Remember to:
                    1) Keep the length of the translated text the same as original text.
                    2) Don't skip or leave any part of the text. All details are very important.
                    3) Identify the Name, Entities and don't translate them, just write them in {target_language}
                    4) Keep the format of the translated text the same as the orignal text.
                    5) You need to format the output as if it was a page of a book. Analyse the content and determine the format, It could be a table of content, title page, or page of a chapter. It should be formatted as that page.
                    6) Only return the translation of the text provided, Don't return anything else.
                    7) Don't return any text in the original language. Only return text in {target_language}
                    8) Identify the headings in the text and bold them
                    9) If you aren't given any text, just return a blank response. Don't return anything other than translated text or blank response"""
                    prompt = enhance_translation_prompt_with_word_pairs(prompt, word_pairs)
                else:
                    prompt = custom_prompt
                    prompt = enhance_translation_prompt_with_word_pairs(prompt, word_pairs)
                st.session_state.translated_text = translate_and_combine_text(edited_text, prompt, source_language, target_language)
        else:
            st.error("No text available to translate.")
        st.session_state['translation_time'] = time.time() - start_time  # End timing
    display_time_taken('translation')
    save_last_state({
        'transcript': st.session_state['transcript'],
        'translated_text': st.session_state['translated_text']
    })
    if 'translated_text' in st.session_state:
        st.session_state.translated_text = st.text_area("Edit the translation:", st.session_state.translated_text, height=600)
        if st.button("Generate Download Link"):
            docx_bytes = convert_text_to_docx_bytes(st.session_state.translated_text)
            st.download_button(
                label="Download Edited Translation",
                data=docx_bytes,
                file_name="edited_translation.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )


    if st.button('Load Last State'):
        last_state = load_last_state()
        if last_state:
            if 'transcript' in last_state:
                st.session_state.transcript = last_state.get('transcript', "")
                edited_text = st.text_area("Content (Edit as needed)", value=st.session_state.transcript, height=300)
            if 'translated_text' in last_state:
                st.session_state.translated_text = last_state.get('translated_text', "")
                translated_text_area = st.text_area("Translated Text", value=st.session_state.translated_text, height=300)
            st.success("Last state loaded successfully.")
        else:
            st.error("No saved state found.")
