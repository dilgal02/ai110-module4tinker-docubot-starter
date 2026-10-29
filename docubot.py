"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re

# Filler words that appear in every doc and would otherwise drown out
# the meaningful query words during scoring
STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "i", "to", "of", "in", "on",
    "for", "and", "or", "what", "which", "where", "how", "there", "any",
    "these", "this", "it", "be", "by", "with", "from", "all",
}

# A section must contain at least this many query word hits to count as evidence.
# Off-topic questions (payments, OAuth, rate limits) score at most 2 on these docs,
# usually from a single common word like "api" or "users".
MIN_EVIDENCE_SCORE = 3

class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Split documents into heading sections so retrieval returns focused snippets
        self.sections = self.split_into_sections(self.documents)  # List of (filename, section_text)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.sections)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    def split_into_sections(self, documents):
        """
        Splits each document at its markdown headings (#, ##, ### ...).
        A section is a heading plus everything under it up to the next heading.
        Returns a list of tuples: (filename, section_text)
        """
        sections = []
        for filename, text in documents:
            for section in re.split(r"\n(?=#{1,6} )", text):
                section = section.strip()
                if section:
                    sections.append((filename, section))
        return sections

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def tokenize(self, text):
        """
        Lowercases text and splits it into words, dropping punctuation and stopwords.
        Underscores also split, so "auth_utils.py" yields "auth", "utils", "py".
        """
        words = re.findall(r"[a-z0-9]+", text.lower())
        return [word for word in words if word not in STOPWORDS]

    def build_index(self, sections):
        """
        Build a tiny inverted index mapping lowercase words to the sections
        they appear in, stored as positions in the sections list.

        Example structure:
        {
            "token": [3, 4, 12],
            "database": [20, 21]
        }
        """
        index = {}
        for i, (_, text) in enumerate(sections):
            for word in set(self.tokenize(text)):
                index.setdefault(word, []).append(i)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        Return a simple relevance score for how well the text matches the query:
        the total number of times the query words appear in the text.
        """
        text_words = self.tokenize(text)
        query_words = set(self.tokenize(query))
        return sum(text_words.count(word) for word in query_words)

    def retrieve(self, query, top_k=3):
        """
        Use the index and scoring function to select the top_k most relevant sections.

        Return a list of (filename, section_text) sorted by score descending.
        Sections scoring below MIN_EVIDENCE_SCORE are dropped, so an empty
        list means the docs hold no useful context for this query.
        """
        # Only score sections that contain at least one query word
        candidates = set()
        for word in self.tokenize(query):
            candidates.update(self.index.get(word, []))

        results = []
        for i in sorted(candidates):
            filename, text = self.sections[i]
            score = self.score_document(query, text)
            has_enough_evidence = score >= MIN_EVIDENCE_SCORE
            if has_enough_evidence:
                results.append((score, filename, text))

        results.sort(key=lambda r: r[0], reverse=True)
        return [(filename, text) for _, filename, text in results][:top_k]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        # No section met MIN_EVIDENCE_SCORE, so refuse instead of showing weak matches
        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        # No section met MIN_EVIDENCE_SCORE, so refuse without calling the LLM
        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
