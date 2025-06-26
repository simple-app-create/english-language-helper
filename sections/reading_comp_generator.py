import random
import json
import os
import streamlit as st  # Added Streamlit
import google.generativeai as genai

# Configure Google Generative AI using Streamlit Secrets
GOOGLE_API_KEY = None
GEMINI_MODEL_CONFIGURED = False

try:
    # Attempt to get the API key from Streamlit secrets
    # The key in secrets.toml should be GEMINI_API_KEY
    GOOGLE_API_KEY = st.secrets.get("GEMINI_API_KEY") 
except Exception as e:
    # This might happen if st.secrets is not available in the environment (e.g. running script outside Streamlit)
    # Or if there's an issue accessing secrets.
    print(f"Warning: Could not access Streamlit secrets. Attempting fallback to OS environment variables if configured: {e}")
    # As a fallback, you could try os.getenv here if you want a layered approach,
    # but the primary method should be st.secrets.
    # For now, we'll assume st.secrets is the main source.
    pass


if not GOOGLE_API_KEY:
    print(
        "Warning: GEMINI_API_KEY not found in Streamlit secrets (e.g., .streamlit/secrets.toml or Streamlit Cloud configuration). LLM calls will be skipped."
    )
    # Optionally, you could fall back to os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") here
    # if you want to support .env files as a secondary local mechanism.
    # e.g., if not GOOGLE_API_KEY: GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY") (after load_dotenv())
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        GEMINI_MODEL_CONFIGURED = True
        print("Google Generative AI configured successfully.")
    except Exception as e:
        print(f"Error configuring Google Generative AI: {e}")
        print(
            "Please check your API key and network connection. LLM calls will be skipped."
        )

# Full list of 50 diverse topics for English language learning
TOPIC_LIST = [
    "Daily Routines in Different Cultures",
    "Popular Hobbies and Leisure Activities",
    "Types of Food and Cuisine Around the World",
    "Festivals and Celebrations",
    "Fashion Trends and Clothing",
    "Family Structures and Relationships",
    "Modes of Transportation",
    "Shopping Habits and Consumerism",
    "Social Etiquette and Customs",
    "Urban vs. Rural Living",
    "The Impact of Artificial Intelligence",
    "Renewable Energy Sources",
    "Space Exploration and Discoveries",
    "The Human Body and Health",
    "Climate Change and Environmental Issues",
    "The Internet and Social Media",
    "Breakthroughs in Medicine",
    "Robotics and Automation",
    "Genetically Modified Foods",
    "The Science of Sleep",
    "Ancient Civilizations (e.g., Egypt, Rome, Maya)",
    "Famous Inventors and Their Inventions",
    "Significant World Wars and Conflicts",
    "The Renaissance Period",
    "Biographies of Influential Leaders",
    "The Industrial Revolution",
    "The Civil Rights Movement",
    "Exploration and Discovery Ages",
    "The Roaring Twenties",
    "The Cold War Era",
    "Different Genres of Music",
    "Famous Painters and Art Movements",
    "Types of Literature (e.g., novels, poetry, drama)",
    "The History of Cinema",
    "Shakespearean Plays and Sonnets",
    "Photography as an Art Form",
    "Architectural Styles",
    "The World of Dance",
    "Famous Authors and Their Works",
    "Mythology and Folklore",
    "Globalization and Its Effects",
    "Education Systems in Different Countries",
    "Poverty and Inequality",
    "Human Rights",
    "The Importance of Volunteering",
    "Wildlife Conservation",
    "The Future of Work",
    "Mental Health Awareness",
    "Sustainable Development Goals",
    "The Role of Media in Society",
    # Culture & Society
    "Taiwanese Hospitality and Friendliness",
    "Confucian Values in Taiwan (e.g., filial piety, respect for elders)",
    "The Concept of 'Face' in Taiwanese Culture",
    "Taiwanese Family Structure and Importance",
    "Religion in Taiwan (Buddhism, Daoism, Folk Religions, Ancestor Worship)",
    "Indigenous Cultures of Taiwan (e.g., Amis, Atayal, Bunun)",
    "Taiwanese Pop Culture (KTV, TV shows, Anime/Manga influence)",
    "Traditional Taiwanese Arts (Opera, Puppet Theater)",
    "Modern Taiwanese Art and Music Scene",
    "Social Etiquette and Customs in Taiwan",
    "Gift-giving etiquette in Taiwan",
    "Public decorum and group harmony",
    # Daily Life & Environment
    "Daily Commute in Taiwan (scooters, public transport)",
    "Convenience Stores in Taiwan (7-Eleven, FamilyMart)",
    "Public Health Care System in Taiwan",
    "Safety and Low Crime Rate in Taiwan",
    "Weather and Climate in Taiwan (subtropical, typhoons)",
    "Air Pollution in Taiwanese Cities",
    "Recycling and Waste Management in Taiwan",
    "Challenges of Living in Big Cities (Taipei: traffic, noise)",
    "Outdoor Activities in Taiwan (hiking, hot springs, cycling)",
    "Taiwan's Natural Beauty (mountains, coastlines, Taroko Gorge)",
    "Learning Mandarin Chinese in Taiwan",
    "Importance of English in Taiwan (academics, career)",
    "Education System and Academic Pressure",
    # Food & Drink
    "Taiwanese Night Markets (types of food, atmosphere)",
    "Bubble Tea (Boba) - its origin and varieties",
    "Famous Taiwanese Dishes (Beef Noodles, Oyster Omelette, Gua Bao)",
    "Street Food Culture in Taiwan",
    "Taiwanese Hot Pot",
    "Pineapple Cakes and other traditional snacks",
    "Local Fruits of Taiwan (seasonal varieties)",
    "Taiwanese Tea Culture (Oolong tea, High Mountain Tea)",
    "Stinky Tofu (description, how it's eaten)",
    "Breakfast in Taiwan (e.g., soy milk, fried dough sticks)",
    "Dining Etiquette in Taiwan",
    "Vegetarian options in Taiwan",
    # History & Politics
    "Taiwan's Colonial History (Dutch, Spanish, Qing Dynasty, Japanese Rule)",
    "The 'Ilha Formosa' - the Beautiful Island",
    "Post-WWII History and KMT Relocation to Taiwan",
    "Chiang Kai-shek and the Republic of China (ROC)",
    "Taiwan's Democratic Transition (lifting of martial law)",
    "The 228 Incident and its significance",
    "Cross-Strait Relations (Taiwan's relationship with mainland China)",
    "Taiwan's International Status and Recognition",
    "Taiwan as an 'Asian Tiger' (economic development)",
    "Key Taiwanese Leaders and their impact",
    "Taiwan's role in global technology and manufacturing (e.g., semiconductors)",
    # Festivals & Celebrations
    "Lunar New Year (Spring Festival) customs and traditions",
    "Lantern Festival (Pingxi Sky Lanterns, Yanshui Beehive Fireworks)",
    "Dragon Boat Festival (dragon boat racing, Zongzi)",
    "Mid-Autumn Festival (Moon Festival, mooncakes, barbecues)",
    "Tomb Sweeping Day (Qingming Festival)",
    "Matsu's Birthday (religious parades and celebrations)",
    "Ghost Festival (Zhongyuan Festival)",
    "Qixi Festival (Chinese Valentine's Day)",
    "National Day (Double Ten Day)",
    "Indigenous Harvest Festivals (e.g., Amis Harvest Festival, Ear-Shooting Festival)",
    "Modern Festivals and Events (e.g., music festivals, balloon festival)",
    # Japanese Anime
    "JoJo's Bizarre Adventure",
    "Hunter x Hunter",
    "Detective Conan",
    "Dragon Ball Z",
    "One Piece",
    "Naruto",
    "Attack on Titan",
    "Fullmetal Alchemist",
]

DIFFICULTY_LIST = [
    "國小一年級",
    "國小二年級",
    "國小三年級",
    "國小四年級",
    "國小五年級",
    "國小六年級",
    "國中一年級",
    "國中二年級",
    "國中三年級",
    "高中一年級",
    "高中二年級",
    "高中三年級",
    "學測",
    "會考",
]

# Constants
DEFAULT_NUM_QUESTIONS = 3
DEFAULT_PARAGRAPH_COUNT = 3
DEFAULT_WORD_COUNT_TARGET = 150
DEFAULT_QUESTION_TYPE = "MCQ"
DEFAULT_MCQ_CHOICES_COUNT = 3


def generate_combined_passage_and_questions_prompt(
    topic: str | None, difficulty_description: str
) -> str:
    current_topic = topic
    if current_topic is None:
        if TOPIC_LIST:
            current_topic = random.choice(TOPIC_LIST)
        else:
            current_topic = "General Knowledge"

    if not isinstance(current_topic, str):
        current_topic = "General Knowledge"

    first_question_example_str = ""
    if DEFAULT_NUM_QUESTIONS > 0:
        # Note: All internal quotes for JSON must be escaped as \\".
        first_question_example_str = (
            f"\n    {{\n"
            f'      \\"questionType\\": \\"READING_COMPREHENSION\\",\n'
            f'      \\"contentAssetId\\": \\"(must match passageAsset.assetId)\\",\n' # Ensure LLM knows to link this
            f'      \\"difficulty\\": {{\n'
            f'        \\"name\\": {{ \\"en\\": \\"{difficulty_description}\\", \\"zh_tw\\": \\"(LLM to generate Chinese translation of {difficulty_description})\\" }},\n'
            f'        \\"stage\\": \\"SENIOR_HIGH\\",\n'
            f'        \\"grade\\": 1,\n'
            f'        \\"level\\": 6\n'
            f"      }},\n"
            f'      \\"learningObjectives\\": [\\"locating specific information\\", \\"vocabulary in context\\"],\n'
            f'      \\"questionText\\": \\"According to the passage, what is one major challenge for life in the deep ocean?\\",\n'
            f'      \\"choices\\": [\n'
            f'        {{ \\"text\\": \\"Abundant sunlight\\", \\"isCorrect\\": false }},\n'
            f'        {{ \\"text\\": \\"Immense pressure\\", \\"isCorrect\\": true }},\n'
            f'        {{ \\"text\\": \\"Warm temperatures\\", \\"isCorrect\\": false }}\n' # No comma after last choice
            f"      ],\n"
            f'      \\"explanation\\": {{\n'
            f'        \\"en\\": \\"The passage explicitly mentions \'immense pressure\' as a characteristic of the deep ocean environment, posing a challenge for life.\\",\n'
            f'        \\"zh_tw\\": \\"文章明確提到「巨大的壓力」是深海環境的一個特徵，對生命構成挑戰。\\"\n'
            f"      }}\n" # No comma after last field in question
            f"    }}"
        )

    additional_questions_example_placeholder = ""
    if DEFAULT_NUM_QUESTIONS > 1:
        additional_questions_example_placeholder = (
            f",\\n" # Comma to separate from the first question
            f"    // ... (and {DEFAULT_NUM_QUESTIONS - 1} more question object(s) like the one above, "
            f"to make a total of {DEFAULT_NUM_QUESTIONS} questions, each correctly formatted as JSON objects)\\n"
        )

    tag_topic_part = "general"
    if current_topic:
        first_word = current_topic.split(" ")[0]
        if first_word:
            tag_topic_part = first_word.lower()

    # Each f-string segment below is a line in the prompt.
    # Newlines within the prompt string are represented by \\n.
    # Quotes within the prompt string (especially for JSON examples) are represented by \\".
    prompt = (
        f"You are an expert AI assistant specializing in creating educational content for English language learners.\n"
        f"Your task is to generate a complete learning module consisting of a reading passage asset and a set of comprehension questions.\n"
        f"The output MUST be a single, minified JSON object with two top-level keys: 'passageAsset' and 'questions_list'.\n\n"
        f"**Overall Specifications for Generation:**\n"
        f"- Topic for passage and questions: '{current_topic}'.\n"
        f"- Target Student Difficulty (for passage and questions, used for 'difficulty.name.en' field): '{difficulty_description}'.\n\n"
        f"**Part 1: `passageAsset` Object Generation**\n"
        f"Create a JSON object for the key `passageAsset`. This object should represent a reading passage and conform to the following structure:\n"
        f"1.  **`assetId`**: (String) Generate a unique identifier string for this passage (e.g., \\\"passage-uuid-placeholder-123\\\" or a real UUID). This ID will be used to link questions to this passage. **This field is mandatory.**\n"
        f"2.  **`assetType`**: (String) Set to \\\"PASSAGE\\\".\n"
        f"3.  **`title`**: (Object) A LocalizedString object with `en` and `zh_tw` keys for the passage title.\n"
        f"    - `en`: (String) Concise English title for the passage related to '{current_topic}'.\n"
        f"    - `zh_tw`: (String) Traditional Chinese translation of the English title.\n"
        f"4.  **`content`**: (String) The full text of an engaging and coherent reading passage about '{current_topic}'.\n"
        f"    - Approximately {DEFAULT_PARAGRAPH_COUNT} paragraphs and {DEFAULT_WORD_COUNT_TARGET} words.\n"
        f"    - Language, vocabulary, and sentence structure must be appropriate for the '{difficulty_description}' level.\n"
        f"5.  **`difficulty`**: (Object) A DifficultyDetail object for the passage:\n"
        f"    - `name`: (Object) A LocalizedString object.\n"
        f"        - `en`: (String) Use the provided Target Student Difficulty: '{difficulty_description}'.\n"
        f"        - `zh_tw`: (String) Traditional Chinese translation of the difficulty name (e.g., if '{difficulty_description}' is 'Intermediate B1', then '中級 B1').\n"
        f"    - `stage`: (String) Educational stage (e.g., 'SENIOR_HIGH', 'JUNIOR_HIGH', 'ELEMENTARY'). Infer from difficulty.\n"
        f"    - `grade`: (Integer) Numerical grade (e.g., 1, 2, 3). Infer from difficulty.\n"
        f"    - `level`: (Integer) Overall difficulty on a 1-10 scale (1 easiest, 10 hardest). Infer from difficulty.\n"
        f"6.  **`description`** (Optional): (Object) A LocalizedString object with `en` and `zh_tw` string properties providing a short description of the passage.\n"
        f"7.  **`learningObjectives`** (Optional): (List of strings) 1-3 strings (e.g., [\\\"understanding narrative sequence\\\", \\\"vocabulary related to {tag_topic_part}\\\"]).\n"
        f"8.  **`tags`** (Optional): (List of strings) 1-3 relevant string keywords (e.g., [\\\"{tag_topic_part}\\\", \\\"reading comprehension\\\"]).\n"
        f"9.  **`source`**: (String) Set to \\\"AI Generated from topic: {current_topic}\\\".\n"
        f"10. **`status`**: (String) Set to \\\"DRAFT\\\".\n"
        f"11. **`version`**: (Integer) Set to `1`.\n\n"
        f"**Part 2: `questions_list` Array Generation**\n"
        f"Create a JSON array for the key `questions_list`. This array should contain exactly {DEFAULT_NUM_QUESTIONS} {DEFAULT_QUESTION_TYPE} comprehension question objects based on the `passageAsset.content` YOU JUST GENERATED.\n"
        f"Each question object in the `questions_list` must have the following structure:\n"
        f"-   **`questionType`**: (String) Set to \\\"READING_COMPREHENSION\\\".\n"
        f"-   **`contentAssetId`**: (String) **This MUST be the exact same string value as the `assetId` you generated for the `passageAsset` in Part 1.** This field links the question to the passage. **This field is mandatory.**\n"
        f"-   **`difficulty`**: (Object) A DifficultyDetail object, structured identically to the `passageAsset.difficulty` object (including the nested `name` object with `en` and `zh_tw` keys) and consistent with it.\n"
        f"-   **`learningObjectives`**: (List of strings) 1-3 strings describing what the question assesses (e.g., [\\\"identifying main idea\\\", \\\"vocabulary in context\\\"]).\n"
        f"-   **`questionText`**: (String) The main question text in English.\n"
        f"-   **`choices`**: (List of {DEFAULT_MCQ_CHOICES_COUNT} objects for MCQ) Each choice object: {{ \\\"text\\\": String, \\\"isCorrect\\\": Boolean }}. Exactly one `isCorrect` must be true.\n"
        f"-   **`explanation`**: (Object) A LocalizedString object with `en` (English explanation) and `zh_tw` (Traditional Chinese explanation), explaining the answer and referring to the passage.\n\n"
        f"**Output Format Instructions (Recap):**\n"
        f"Your entire response MUST be a single, minified JSON object with two top-level keys: `passageAsset` (structured as per Part 1) and `questions_list` (structured as per Part 2). No other text or explanations outside this JSON object. Do not use markdown backticks (e.g., ```json) around the JSON output.\n\n"
        f"**Example of the complete JSON output structure (your actual output must be minified, this example is indented for readability):**\n"
        f"{{\n"
        f"  \\\"passageAsset\\\": {{\n"
        f"    \\\"assetId\\\": \\\"(example-passage-uuid-from-part1)\\\",\n"
        f"    \\\"assetType\\\": \\\"PASSAGE\\\",\n"
        f"    \\\"title\\\": {{\n"
        f"      \\\"en\\\": \\\"The Mysteries of the Deep Ocean\\\",\n"
        f"      \\\"zh_tw\\\": \\\"深海的奧秘\\\"\n"
        f"    }},\n"
        f"    \\\"content\\\": \\\"The deep ocean, a realm of perpetual darkness... (Full passage text generated here, approximately {DEFAULT_WORD_COUNT_TARGET} words, {DEFAULT_PARAGRAPH_COUNT} paragraphs, suitable for '{difficulty_description}' level learners.)\\\",\n"
        f"    \\\"difficulty\\\": {{\n"
        f"      \\\"name\\\": {{ \\\"en\\\": \\\"{difficulty_description}\\\", \\\"zh_tw\\\": \\\"(LLM to generate Chinese translation of {difficulty_description})\\\" }},\n"
        f"      \\\"stage\\\": \\\"SENIOR_HIGH\\\",\n"
        f"      \\\"grade\\\": 1,\n"
        f"      \\\"level\\\": 6\n"
        f"    }},\n"
        f"    \\\"description\\\": {{\n"
        f"      \\\"en\\\": \\\"An informative passage about the unique creatures and environment of the deep ocean...\\\",\n"
        f"      \\\"zh_tw\\\": \\\"一篇關於深海獨特生物與環境的知識性文章...\\\"\n"
        f"    }},\n"
        f"    \\\"learningObjectives\\\": [\\\"understanding scientific vocabulary related to marine biology\\\"],\n"
        f"    \\\"tags\\\": [\\\"ocean\\\", \\\"science\\\", \\\"nature\\\"],\n"
        f"    \\\"source\\\": \\\"AI Generated from topic: {current_topic}\\\",\n"
        f"    \\\"status\\\": \\\"DRAFT\\\",\n"
        f"    \\\"version\\\": 1\n"
        f"  }},\n"
        f"  \\\"questions_list\\\": ["
        + first_question_example_str  # This string is already formatted for JSON
        + additional_questions_example_placeholder  # This string is also formatted
        + "\n  ]\n" # Closing the questions_list array
        f"}}\n" # Closing the main JSON object
    )
    return prompt


def call_gemini_llm(
    prompt_text: str, model_name: str = "gemini-2.5-flash"
) -> str | None:
    if not GEMINI_MODEL_CONFIGURED:
        print("Google Generative AI not configured. Cannot call LLM.")
        return None

    try:
        print(f"Sending prompt to Gemini model: {model_name}...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt_text)

        generated_text = None
        if response and hasattr(response, "text") and response.text:
            generated_text = response.text
        elif response and response.parts:
            generated_text = "".join(
                part.text
                for part in response.parts
                if hasattr(part, "text") and part.text
            )

        if generated_text:
            cleaned_response = generated_text.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            elif cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]

            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]

            print("LLM response received and cleaned.")
            return cleaned_response.strip()

        print("Error: LLM response was empty or did not contain text.")
        if response and hasattr(response, "prompt_feedback"):
            print(f"Prompt Feedback: {response.prompt_feedback}")
        return None

    except Exception as e:
        print(f"Error calling Google Gemini LLM: {e}")
        if "response" in locals() and response:
            try:
                print(f"LLM response object type (on error): {type(response)}")
                if hasattr(response, "prompt_feedback"):
                    print(f"Prompt Feedback (on error): {response.prompt_feedback}")
                if hasattr(response, "candidates") and response.candidates:
                    print(f"First candidate (on error): {response.candidates[0]}")
            except Exception as e_resp:
                print(f"Could not print detailed response object information: {e_resp}")
        return None


if __name__ == "__main__":
    print("Starting reading comprehension generator script...\n")

    example_topic_explicit = "The Impact of Social Media on Teenagers"
    example_difficulty_desc = "Upper-Intermediate B2"

    print(f"--- Generating LLM Prompt (Explicit Topic: '{example_topic_explicit}') ---")
    generated_prompt_explicit = generate_combined_passage_and_questions_prompt(
        example_topic_explicit, example_difficulty_desc
    )
    # print("Generated Prompt (Explicit Topic):\n", generated_prompt_explicit) # Uncomment for debugging

    llm_output_data_explicit = None
    if GEMINI_MODEL_CONFIGURED:
        print("\n--- Calling Google Gemini LLM (Explicit Topic) ---")
        llm_response_explicit = call_gemini_llm(generated_prompt_explicit)

        if llm_response_explicit:
            print(
                "\n--- Raw Minified LLM Response (Explicit Topic, first 200 chars) ---"
            )
            print(
                llm_response_explicit[:200] + "..."
                if len(llm_response_explicit) > 200
                else llm_response_explicit
            )
            print("\n--- Attempting to Parse LLM Response (Explicit Topic) ---")
            try:
                full_llm_output = json.loads(llm_response_explicit)

                passage_asset_data = full_llm_output.get("passageAsset")
                questions_list_data = full_llm_output.get("questions_list")

                if passage_asset_data:
                    print("\n--- Parsed Passage Asset Data ---")
                    print(json.dumps(passage_asset_data, indent=2, ensure_ascii=False))
                else:
                    print("\n--- No 'passageAsset' key found in LLM response ---")

                if questions_list_data:
                    print("\n--- Parsed Questions List Data ---")
                    print(json.dumps(questions_list_data, indent=2, ensure_ascii=False))
                else:
                    print("\n--- No 'questions_list' key found in LLM response ---")

                llm_output_data_explicit = full_llm_output
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from LLM response (Explicit Topic): {e}")
                print("Raw response that caused error was (first 500 chars):")
                print(llm_response_explicit[:500])
        else:
            print("Failed to get a valid response from the LLM for the explicit topic.")
    else:
        print(
            "\nSkipping LLM call for explicit topic as Google Generative AI is not configured."
        )

    print("\n" + "=" * 50 + "\n")

    print(
        f"--- Generating LLM Prompt (Random Topic, Difficulty: {example_difficulty_desc}) ---"
    )
    generated_prompt_random = generate_combined_passage_and_questions_prompt(
        None, example_difficulty_desc
    )
    # print("Generated Prompt (Random Topic):\n", generated_prompt_random) # Uncomment for debugging

    llm_output_data_random = None
    if GEMINI_MODEL_CONFIGURED:
        print("\n--- Calling Google Gemini LLM (Random Topic) ---")
        llm_response_random = call_gemini_llm(generated_prompt_random)

        if llm_response_random:
            print("\n--- Raw Minified LLM Response (Random Topic, first 200 chars) ---")
            print(
                llm_response_random[:200] + "..."
                if len(llm_response_random) > 200
                else llm_response_random
            )
            print("\n--- Attempting to Parse LLM Response (Random Topic) ---")
            try:
                full_llm_output_random = json.loads(llm_response_random)

                passage_asset_data_random = full_llm_output_random.get("passageAsset")
                questions_list_data_random = full_llm_output_random.get(
                    "questions_list"
                )

                if passage_asset_data_random:
                    print("\n--- Parsed Passage Asset Data (Random Topic) ---")
                    print(
                        json.dumps(
                            passage_asset_data_random, indent=2, ensure_ascii=False
                        )
                    )
                else:
                    print(
                        "\n--- No 'passageAsset' key found in LLM response (Random Topic) ---"
                    )

                if questions_list_data_random:
                    print("\n--- Parsed Questions List Data (Random Topic) ---")
                    print(
                        json.dumps(
                            questions_list_data_random, indent=2, ensure_ascii=False
                        )
                    )
                else:
                    print(
                        "\n--- No 'questions_list' key found in LLM response (Random Topic) ---"
                    )

                llm_output_data_random = full_llm_output_random
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from LLM response (Random Topic): {e}")
                print("Raw response that caused error was (first 500 chars):")
                print(llm_response_random[:500])
        else:
            print("Failed to get a valid response from the LLM for the random topic.")
    else:
        print(
            "\nSkipping LLM call for random topic as Google Generative AI is not configured."
        )

    print("\n\n--- Script Finished ---")
    if not GEMINI_MODEL_CONFIGURED:
        print(
            "Note: LLM calls were skipped because Google API Key was not properly configured."
        )
    elif not llm_output_data_explicit and not llm_output_data_random:
        print("Note: No successful data was generated from the LLM in this run.")
