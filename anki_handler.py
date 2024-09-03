import json
import requests
from aqt import mw
import os


def find_media_folder():
    print(f"Searching for Anki media folder...:")
    home_dir = os.path.expanduser("~")
    media_folder = os.path.join(home_dir, 'AppData', 'Roaming', 'Anki2', 'User 1', 'collection.media')

    if os.path.exists(media_folder):
        print(f"Anki media folder found at: {media_folder}")
        return media_folder
    else:
        print("Anki media folder not found.")
        return None


class Anki:
    def __init__(self, deck_id: str, media_folder: str = None):
        self.deck_id = deck_id
        self.media_folder = find_media_folder()

    def check(self):
        hostname = "http://localhost:8765"
        response = os.system("ping -c 1 -w2 " + hostname + " > /dev/null 2>&1")

        if response == 0:
            print(f"Anki connection succeeded.")
        else:
            print(f"Unable to communicate with Anki!")

    # deprecated
    def add_card(self, card_type, f_1, t_1, f_2, t_2):
        print("Adding card to Anki! :D")
        model = mw.col.models.by_name(card_type)  # Replace "Basic" with your card type name
        new_note = mw.col.new_note(model)
        new_note[f_1] = t_1  # Replace "Front" with your field name
        new_note[f_2] = t_2  # Replace "Back" with your field name
        did = mw.col.decks.id(self.deck_id)  # Replace "Geography" with your deck name
        mw.col.add_note(new_note, did)

    # deprecated in favor of add_cloze_card which uses anki connect
    def add_cloze(self, t_1, t_2):
        self.add_card("Cloze", "Text", t_1, "Back Extra", t_2)

    def add_cloze_card(self, t_1, t_2):
        url = 'http://localhost:8765'
        headers = {'Content-Type': 'application/json'}
        payload = {
            'action': 'addNote',
            'version': 6,
            'params': {
                'note': {
                    'modelName': 'Cloze',
                    'deckName': self.deck_id,
                    'fields': {
                        'Text': t_1,
                        'Back Extra': t_2
                    },
                    'tags': [],
                    "options": {
                        "allowDuplicate": False,
                        "duplicateScope": "deck",
                        "duplicateScopeOptions": {
                            "deckName": "Default",
                            "checkChildren": False,
                            "checkAllModels": False
                        }
                    }
                }
            }
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        result = response.json()
        print(result)

    def get_media_folder(self):
        return self.media_folder
