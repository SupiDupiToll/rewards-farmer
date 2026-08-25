import json
import os
import random
import urllib.request
import urllib.error
from typing import Generator

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Your OpenRouter API key. Get one from https://openrouter.ai/settings/keys
# Set it via the OPENROUTER_API_KEY environment variable.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Any model identifier from https://openrouter.ai/models. The default
# "openrouter/free" is OpenRouter's Free Models Router (https://openrouter.ai/openrouter/free),
# which selects free models at random. Override with OPENROUTER_MODEL.
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

DEFAULT_SYSTEM_PROMPT_FOR_SEARCH_QUEST = (
	"You are a helpful assistant tasked with creating a search query based on a directive. "
	"Output nothing but the search query you create, and do not include any additional commentary or explanation. "
	"Do not include any labels or quotes. "
	"The search query must be the only output, and do not format the query as an imperative to 'search for' something. "
	"Imagine that your output will be fed directly into a search engine as you provide it. "
	"For example, if the directive is 'Search on Bing for the latest news about space exploration', you might output 'latest news space exploration'. "
	"Outputting 'search on Bing for the latest news about space exploration' or 'search bing.com/news for space exploration' would be incorrect, "
	"as those answers include instructions to perform a search rather than just the search query itself. "
	"Additionally, be specific, e.g. if a prompt asks you to search for vacation flights, include "
	"a specific destination rather than just searching 'vacation flights'. The current year is 2026. "
	"Make your query concise, ideally 6 words or less, and do not include any punctuation. "
)

DEFAULT_USER_PROMPT_FOR_SEARCH_QUEST_WITHOUT_DESC = """Base your search query on the following task description: """

DEFAULT_SYSTEM_PROMPT_FOR_SEARCH_POINTS = (
	"The user is interested in learning more about topics related to a word that will be given to you. "
	"Your task is to come up with subsequent search queries that relate to each other, each one branching out "
	"from the previous one so that the user can explore a topic in depth. Your first search query should be "
	"based on the word that the user gives you, and each subsequent search query should be at least remotely based on the previous ones. "
	"Output only the single search query you come up with and do not include any additional commentary or explanation. Do not include any labels or quotes. "
	"The search queries should ideally be short (6 words max) and do not need to be fully fledged questions, but they should be unique. The current year is 2026."
)

DEFAULT_USER_PROMPT_FOR_SEARCH_POINTS_WITHOUT_DESC = """Generate the first search query based on the following word: """

USER_PROMPT_FOR_SEARCH_QUERY_CONTINUATION = """Generate the next search query."""

def get_llm_response(messages: list[dict[str, str]], model: str = OPENROUTER_MODEL) -> str:
	"""Send a chat request to OpenRouter and return the assistant's reply."""
	if not OPENROUTER_API_KEY:
		raise RuntimeError(
			"OPENROUTER_API_KEY is not set.\n\n"
			"1. Create an account at https://openrouter.ai and get an API key at\n"
			"   https://openrouter.ai/settings/keys (button 'Create Key', e.g. 'sk-or-...').\n"
			"2. Make the key available as an environment variable, for example:\n\n"
			"   Linux/macOS:  export OPENROUTER_API_KEY='sk-or-...'\n"
			"   Windows CMD:   set OPENROUTER_API_KEY=sk-or-...\n"
			"   PowerShell:    $env:OPENROUTER_API_KEY='sk-or-...'\n"
			"   Or put it in a .env file and load it before running the script.\n"
			"\nOptionally set OPENROUTER_MODEL to override the model (default openrouter/free)."
		)

	payload = json.dumps({
		"model": model,
		"messages": messages,
	}).encode("utf-8")

	request = urllib.request.Request(
		OPENROUTER_URL,
		data=payload,
		headers={
			"Authorization": f"Bearer {OPENROUTER_API_KEY}",
			"Content-Type": "application/json",
		},
	)

	try:
		with urllib.request.urlopen(request) as response:
			data = json.loads(response.read().decode("utf-8"))
	except urllib.error.HTTPError as e:
		raise RuntimeError(f"OpenRouter request failed with HTTP {e.code}: {e.read().decode('utf-8')}") from e

	return data["choices"][0]["message"]["content"]

def get_search_query_from_task_description(task_description: str) -> str:
	# compat
	if "lyrics of your favorite song" in task_description.lower(): return "sweet caroline lyrics"

	messages = [
		{
			"role": "system",
			"content": DEFAULT_SYSTEM_PROMPT_FOR_SEARCH_QUEST
		},
		{
			"role": "user",
			"content": DEFAULT_USER_PROMPT_FOR_SEARCH_QUEST_WITHOUT_DESC + task_description
		}
	]

	while not (response := get_llm_response(messages)): pass # ensure non-empty response

	return response.lower()

def get_related_search_queries(seed_word: str, num_queries: int=20) -> Generator[str, None, None]:
	messages = [
		{
			"role": "system",
			"content": DEFAULT_SYSTEM_PROMPT_FOR_SEARCH_POINTS
		},
		{
			"role": "user",
			"content": DEFAULT_USER_PROMPT_FOR_SEARCH_POINTS_WITHOUT_DESC + seed_word
		}
	]

	for _ in range(num_queries):
		while not (response := get_llm_response(messages)): pass # ensure non-empty response

		yield response.lower()

		messages.append({
			"role": "assistant",
			"content": response
		})

		messages.append({
			"role": "user",
			"content": USER_PROMPT_FOR_SEARCH_QUERY_CONTINUATION
		})

NOUNS = [
	noun.strip().lower() for noun in open("nouns.txt", "r").read().splitlines()
	if len(noun.strip()) >= 3
]

def get_random_noun() -> str:
	return random.choice(NOUNS)