import datetime
import json
import os
import requests
from dataclasses import dataclass
from bs4 import BeautifulSoup
from elevenlabs_handler import ElevenLabs
from anki_handler import Anki
from dotenv import load_dotenv
import pycountry


@dataclass
class Config:
    elevenlabs: ElevenLabs = None
    anki: Anki = None
    lang_from: str = ""
    lang_to: str = ""


def parse_wr_td(td_element):
    # Extract text while excluding the text of nested <em> tags
    for em_tag in td_element.find_all("em"):
        em_tag.decompose()  # Remove the <em> tag and its content

    # Get text from the modified <td> element
    text = td_element.get_text(strip=True)

    return text


def extract_wr_phrases_and_translations(word, config):
    url = f"https://www.wordreference.com/{config.lang_from}{config.lang_to}/{word}"
    print(f"Requesting data from {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch WordReference data. HTTP Status Code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr")
    filtered_rows = [row for row in rows if 'class' in row.attrs and row['class'][0] in ['even', 'odd']]
    # print(*filtered_rows, sep='\n')

    # Get the class of the first row. Either 'even' or 'odd'.
    row_state = filtered_rows[0]['class'][0]

    # Complete list of words, definitions, phrases, and translations
    word_data = []

    i = 0
    while i < len(filtered_rows):  # Loop over all filtered rows

        row = filtered_rows[i]
        row_class = row.get("class")[0]

        if not row_class:
            i += 1
            continue  # Skip rows without a class attribute

        # Initialize data structure for each word entry
        entry = {"definitions": [], "examples": []}

        l_examples = []
        t_examples = []
        examples = []

        # Ensure we are still processing the same group of rows
        while i < len(filtered_rows) and row_class == row_state:
            # Search for the word, definition, and translations
            word = row.find("td", class_=f'{config.lang_from.capitalize()}Wrd')
            part_of_speech = row.find("em", class_="POS2")
            definition = row.find("td", class_='ToWrd')
            l_example = row.find("td", class_=f'{config.lang_from.capitalize()}Ex')  # Target language example
            t_example = row.find("td", class_='ToEx')  # Translated example

            if part_of_speech:  # This has to come first because when using parse_wr_td it decomposes the em tag
                entry["part_of_speech"] = part_of_speech.get_text()
            if word:
                entry["word"] = parse_wr_td(word)
            if definition:
                entry["definitions"].append(parse_wr_td(definition))
            if l_example:
                l_examples.append(l_example.get_text())
            if t_example:
                t_examples.append(t_example.get_text())

            # Move to the next row
            i += 1
            if i < len(filtered_rows):
                row = filtered_rows[i]
                row_class = row.get("class")[0]

        # Handle examples based on the number of l_examples and t_examples
        if l_examples and not t_examples:
            # Only local examples, add them directly
            for example in l_examples:
                examples.append({"example": example})

        elif len(l_examples) == len(t_examples):
            # Equal number of local and translated examples, pair them
            for l, t in zip(l_examples, t_examples):
                examples.append({
                    "example": l,
                    "translations": [t]
                })

        elif l_examples and len(t_examples) > len(l_examples):
            # More translated examples, map all under the single local example
            for l in l_examples:
                example_dict = {"example": l, "translations": t_examples}
                examples.append(example_dict)

        elif l_examples and len(l_examples) > len(t_examples):
            # More translated examples, map all under the single local example
            new_t_examples = []
            for ex in t_examples:
                new_t_examples.extend(ex.split("//"))

            for l, t in zip(l_examples, new_t_examples):
                examples.append({
                    "example": l,
                    "translations": [t]
                })

        # Store the examples list in the entry
        entry["examples"].extend(examples)
        # Add the entry to the word_data list
        word_data.append(entry)

        # Move to the next definition group
        if i < len(filtered_rows):
            row_state = filtered_rows[i].get("class")[0]  # Update row_state to the next class

    return word_data


def extract_collins_phrases_and_translations(word, config):
    url = f"https://www.wordreference.com/dictionary/getcollins/{config.lang_from}{config.lang_to}/{word}?slide=1"
    print(f"Requesting data from {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch Collins data. HTTP Status Code: {response.status_code}")
        return []
    data = response.text
    soup = BeautifulSoup(data, "html.parser")
    container = soup.find("div", {"id": "collinsdiv"})

    pairs = []
    last_phrase = None

    for element in container.find_all(["span", "br"], recursive=True):
        if "phrase" in element.get("class", []):
            last_phrase = element.get_text(strip=True)
        elif "translation" in element.get("class", []) and last_phrase:
            translation = element.get_text(strip=True)
            pairs.append((last_phrase, translation))
            last_phrase = None  # Reset after pairing

    return pairs


def generate_options(data):
    options = []

    for item in data:
        # Prepare the main word and definition line
        word = item.get("word", "No word")
        definitions = ", ".join(item.get("definitions", ["No definitions"]))
        options.append(( word, definitions))

        # Prepare examples and translations
        examples = item.get("examples", [])
        for example_item in examples:
            example_text = example_item.get("example", "No example")
            translations = example_item.get("translations", ["No Translation"])

            for translation in translations:
                options.append((example_text, translation))

    return options


def print_options(options):
    print("Please select which phrase/word to use on your card:")
    for index, option, in enumerate(options):
        print(f"{index + 1}. {option[0]} -> {option[1]}")


def select_image(save_path):
    while True:
        # Ask the user for the image URL
        image_url = input("Enter an image URL for your card\n If you don't want an image, enter \"NONE\": ").strip()

        if image_url.lower() == "none":
            return None

        if not image_url:
            print("No URL provided. Please enter a valid image URL.")
            continue

        try:
            # Send a GET request to fetch the image
            response = requests.get(image_url)
            response.raise_for_status()  # Check if the request was successful

            # Check if the response is an image
            content_type = response.headers.get('Content-Type')
            if 'image' not in content_type:
                print("The URL does not point to an image. Please provide a valid image URL.")
                continue

            # Extract the image file name from the URL
            image_name = os.path.basename(image_url)
            full_path = os.path.join(save_path, image_name)

            # Write the image to the specified location
            with open(full_path, "wb") as file:
                file.write(response.content)

            print(f"Image successfully downloaded and saved to: {full_path}")
            return image_name

        except requests.RequestException as e:
            print(f"Failed to download image. Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


def generate_card(word, config):
    print(f"Generating Card for '{word}'...")
    wr_data = extract_wr_phrases_and_translations(word, config)
    filtered_data = [item for item in wr_data if item.get("word")]
    options = generate_options(filtered_data)
    print_options(options)

    selected_phrase: tuple = ()
    choice = 0

    while not selected_phrase:
        try:
            choice = int(input(f"Enter the number of the phrase you want (1-{len(options)}): "))
            if 1 <= choice <= len(options):
                selected_phrase = options[choice - 1]
                print(f"You selected: {selected_phrase}")
            else:
                print(f"Invalid choice. Please enter a number between 1 and {len(options)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    tts_file_name = f"pronunciation_{config.lang_from}_{selected_phrase[0].replace(' ', '_')}.mp3"
    config.elevenlabs.tts(selected_phrase[0], tts_file_name)

    image_name = select_image(config.anki.media_folder)

    def format_html(translations, sentence, t_sentence):
        # In the language sentence, bold the word
        formatted_sentence = sentence.replace(word, f"<b><i>{word}</i></b>")

        # In the translated sentence, bold the translated word and make it clozed
        formatted_t_sentence = t_sentence
        for translation in translations:
            if translation in formatted_t_sentence:
                formatted_t_sentence = formatted_t_sentence.replace(translation, f"<b><i>{{{{c1::{translation}}}}}</i></b>")
            elif translation.capitalize() in formatted_t_sentence:
                formatted_t_sentence = formatted_t_sentence.replace(translation.capitalize(), f"<b><i>{{{{c1::{translation.capitalize()}}}}}</i></b>")

        html_payload = f"""
        <div style="text-align: center;">{formatted_sentence}</div>
        <div style="text-align: center;">{formatted_t_sentence}<br></div>
        <div style="text-align: center; max-height: 400px;">
            <img alt="Image" src="{image_name}"><br>
        </div>
        <div style="text-align: center;">
            <hr>[sound:{tts_file_name}]<br><br><br>
        </div>
        """

        return html_payload

    definitions = filtered_data[choice - 1]["definitions"]
    example_sentence = selected_phrase[0]
    translation_sentence = selected_phrase[1]  # Ensure this is the translated sentence

    html_payload = format_html(definitions, example_sentence, translation_sentence)
    config.anki.add_cloze_card(html_payload, "")

def set_languages(l1, l2, config):
    fl1 = pycountry.languages.get(alpha_2=l1)
    fl2 = pycountry.languages.get(alpha_2=l2)
    if fl1 and fl2:
        config.lang_from = l1
        config.lang_to = l2
        print(f"Successfully set languages: {fl1.name} -> {fl2.name}")


def handle_command(command, config):
    parts = command.strip().split()

    if len(parts) == 0:
        return

    main_command = parts[0].lower()

    if main_command == "exit":
        print("Exiting...")
        return False

    elif main_command == "gen":
        if len(parts) >= 3 and parts[1].lower() == "card":
            word = " ".join(parts[2:])
            generate_card(word, config)
        else:
            print("Usage: generate card <word>")

    elif main_command == "lang":
        if len(parts) >= 3:
            set_languages(parts[1].lower(), parts[2].lower(), config)
        else:
            print(
                "Usage: language <lang_from> <lang_to>\n <lang_from> and <lang_to> must be the 2 character abbreviation of the "
                "language.\n i.e.\nen = English\nfr = French")

    elif main_command == "find" and len(parts) == 2 and parts[1].lower() == "anki":
        print(config.anki.get_media_folder())

    elif main_command == "check" and len(parts) == 2 and parts[1].lower() == "anki":
        config.anki.check()

    else:
        print(f"Unknown command: {command}")

    return True


def main():
    load_dotenv()
    print("===[AnkiLangGen]===")

    config = Config()
    anki = Anki("French::French Phrases")
    config.anki = anki
    elevenlabs = ElevenLabs(os.getenv("ELEVENLABS_API_KEY"),
                            "rgFgMEXfdGwXCYio7I0J",
                            config.anki.media_folder)
    config.elevenlabs = elevenlabs

    while True:
        command = input("> ")
        if not handle_command(command, config):
            break


if __name__ == "__main__":
    main()
