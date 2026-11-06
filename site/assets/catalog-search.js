// Catalog search for the website, ported from QueryService
// (src/benchmark_radar/query.py, ranking "bm25f_v3").
//
// The site used to match one folded substring against name, aliases,
// publisher, modality and categories. It never read descriptions, so a task
// the catalog describes only in prose ("weather forecasting") returned 0 of 0
// on the site while the CLI, HTTP surface and Skill found it (issue #710).
// docs/query-surfaces.md makes QueryService the single source of truth and
// forbids interface-specific ranking, so this module mirrors its tokenizer,
// candidate rule and sort key instead of inventing a site variant.
// tests/test_catalog_search_parity.py runs both over the same records and
// fails when their candidates or order diverge.

const FIELD_ORDER = ["name", "description", "categories", "publisher", "modality", "languages", "source"];
const FIELD_WEIGHTS = {
  name: 5.0,
  description: 1.0,
  categories: 2.5,
  publisher: 0.6,
  modality: 1.2,
  languages: 0.3,
  source: 0.2,
};
const BM25_K1 = 1.2;
const BM25_B = 0.75;
const NAME_MATCH_MULTIPLIERS = [3.0, 1.5, 0.75];
const PHRASE_MULTIPLIER = 0.5;
const MIN_PREFIX_LENGTH = 2;
// Han ideographs plus hiragana and katakana, which share unspaced text with Han.
const CJK_CHARS =
  "々ぁ-ゟァ-ヺー-ヿㇰ-ㇿ㐀-䶿一-鿿豈-﫿";
// Latin letters outside ASCII stay out of the word alternative, as in Python,
// so Latin text keeps its ASCII tokens.
const LATIN_EXTENDED = "À-ʯḀ-ỿⱠ-Ɀ꜠-ꟿꬰ-꭯";
// Python's [^\W\d_] is a letter or a non-decimal numeric character.
const TOKEN_PARTS = new RegExp(
  `[a-z0-9]+|(?<cjk>[${CJK_CHARS}]+)|(?:(?![${CJK_CHARS}${LATIN_EXTENDED}])[\\p{L}\\p{Nl}\\p{No}])+`,
  "gu",
);
const ASCII = /^[\x00-\x7f]*$/;

// str.casefold() differs from toLowerCase() on a handful of letters. These are
// the ones that survive NFKD and appear in catalog text.
function casefold(value) {
  return value.toLowerCase().replace(/ß/g, "ss").replace(/ς/g, "σ");
}

export function searchTokens(value) {
  const normalized = casefold(String(value || "").normalize("NFKD"));
  const tokens = [];
  for (const match of normalized.matchAll(TOKEN_PARTS)) {
    let part = match[0];
    if (match.groups.cjk !== undefined) {
      // Han and kana have no spaces between words, so adjacent character pairs
      // let a short query find a longer description without treating every
      // shared single character as a match. NFKD split voiced kana from their
      // marks, so recompose first.
      const chars = Array.from(part.normalize("NFC"));
      for (let index = 0; index < chars.length - 1; index += 1) tokens.push(chars[index] + chars[index + 1]);
      if (chars.length === 1) tokens.push(chars[0]);
    } else {
      tokens.push(part);
    }
  }
  return tokens;
}

function fieldText(value) {
  if (Array.isArray(value)) return value.map(String).join(" ");
  return value ? String(value) : "";
}

function countTokens(tokens) {
  const counts = new Map();
  for (const token of tokens) counts.set(token, (counts.get(token) || 0) + 1);
  return counts;
}

function buildCorpus(records) {
  const documents = [];
  const documentFrequency = new Map();
  const totalAscii = Object.fromEntries(FIELD_ORDER.map((field) => [field, 0]));
  const totalUnicode = Object.fromEntries(FIELD_ORDER.map((field) => [field, 0]));
  for (const record of records) {
    const fieldTokens = {};
    for (const field of FIELD_ORDER) fieldTokens[field] = searchTokens(fieldText(record[field]));
    // Registered aliases are name evidence for every source.
    if (record.aliases && record.aliases.length) {
      fieldTokens.name = searchTokens(`${fieldText(record.name)} ${fieldText(record.aliases)}`);
    }
    const fieldCounts = {};
    const asciiLengths = {};
    const unicodeLengths = {};
    const allTokens = new Set();
    for (const field of FIELD_ORDER) {
      const tokens = fieldTokens[field];
      fieldCounts[field] = countTokens(tokens);
      asciiLengths[field] = tokens.filter((token) => ASCII.test(token)).length;
      unicodeLengths[field] = tokens.length - asciiLengths[field];
      totalAscii[field] += asciiLengths[field];
      totalUnicode[field] += unicodeLengths[field];
      for (const token of tokens) allTokens.add(token);
    }
    for (const token of allTokens) documentFrequency.set(token, (documentFrequency.get(token) || 0) + 1);
    documents.push({ record, fieldTokens, fieldCounts, asciiLengths, unicodeLengths, allTokens });
  }
  const count = documents.length;
  const averages = {};
  const unicodeAverages = {};
  for (const field of FIELD_ORDER) {
    averages[field] = count ? totalAscii[field] / count : 0;
    unicodeAverages[field] = count ? totalUnicode[field] / count : 0;
  }
  return { documents, documentFrequency, averages, unicodeAverages };
}

function idf(term, corpus) {
  const count = corpus.documents.length;
  const frequency = corpus.documentFrequency.get(term) || 0;
  return Math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5));
}

function containsTokens(haystack, needle) {
  if (!needle.length || needle.length > haystack.length) return false;
  for (let index = 0; index <= haystack.length - needle.length; index += 1) {
    if (needle.every((token, offset) => haystack[index + offset] === token)) return true;
  }
  return false;
}

// The word still being typed: the last query word also matches the words that
// start with it. ASCII only, as in Python, because CJK tokens are character pairs.
function prefixTerm(queryTokens) {
  const last = queryTokens[queryTokens.length - 1];
  return Array.from(last).length >= MIN_PREFIX_LENGTH && ASCII.test(last) ? last : null;
}

// Per field, how many tokens start with `term` without being `term`.
function prefixCounts(document, term) {
  const counts = {};
  for (const field of FIELD_ORDER) {
    let total = 0;
    for (const [token, count] of document.fieldCounts[field]) {
      if (token !== term && token.startsWith(term)) total += count;
    }
    if (total) counts[field] = total;
  }
  return counts;
}

function nameMatchTier(nameTokens, queryTokens) {
  const same = (a, b) => a.length === b.length && a.every((token, index) => token === b[index]);
  if (same(nameTokens, queryTokens)) return 0;
  const head = nameTokens.slice(0, queryTokens.length);
  if (same(head, queryTokens)) return 1;
  if (
    head.length === queryTokens.length &&
    prefixTerm(queryTokens) !== null &&
    same(head.slice(0, -1), queryTokens.slice(0, -1)) &&
    head[head.length - 1].startsWith(queryTokens[queryTokens.length - 1])
  ) {
    return 1;
  }
  if (containsTokens(nameTokens, queryTokens)) return 2;
  return null;
}

function bm25fScore(document, queryTokens, corpus, prefixHits) {
  let score = 0.0;
  for (const term of queryTokens) {
    let weightedFrequency = 0.0;
    for (const field of FIELD_ORDER) {
      let frequency = document.fieldCounts[field].get(term) || 0;
      // A word that exists in the corpus keeps its whole-word scores; only an
      // unknown fragment such as "saf" takes its score from prefix hits.
      if (term === queryTokens[queryTokens.length - 1] && !corpus.documentFrequency.get(term)) {
        frequency += prefixHits[field] || 0;
      }
      if (!frequency) continue;
      // Length normalization keeps ASCII terms on their original token
      // population so Unicode support does not reorder English hits.
      const ascii = ASCII.test(term);
      const fieldLength = ascii ? document.asciiLengths[field] : document.unicodeLengths[field];
      const averageLength = (ascii ? corpus.averages[field] : corpus.unicodeAverages[field]) || 1.0;
      const lengthNormalization = 1.0 - BM25_B + BM25_B * (fieldLength / averageLength);
      weightedFrequency += (FIELD_WEIGHTS[field] * frequency) / lengthNormalization;
    }
    if (weightedFrequency) {
      score += idf(term, corpus) * ((weightedFrequency * (BM25_K1 + 1.0)) / (BM25_K1 + weightedFrequency));
    }
  }
  return score;
}

function present(value) {
  return value !== undefined && value !== null && value !== "";
}

// Mirrors the Python sort key: retrieval score, IDF coverage, name tier,
// completeness, name length, folded name, key. Also returns the query words the
// record lacks, QueryService's `missing_tokens`.
function sortKey(document, queryTokens, corpus) {
  const lastTerm = prefixTerm(queryTokens);
  const prefixHits = lastTerm ? prefixCounts(document, lastTerm) : {};
  if (!queryTokens.some((token) => document.allTokens.has(token)) && !Object.keys(prefixHits).length) return null;
  const matched = new Set();
  const matchedFields = [];
  for (const field of FIELD_ORDER) {
    let hits = false;
    for (const token of queryTokens) {
      if (document.fieldCounts[field].has(token)) {
        matched.add(token);
        hits = true;
      }
    }
    if (prefixHits[field]) {
      matched.add(lastTerm);
      hits = true;
    }
    if (hits) matchedFields.push(field);
  }
  // Issue #432: a multi-word query whose only hit is one token in
  // description only is noise, not evidence. Mirrors QueryService.
  if (
    queryTokens.length > 1 &&
    matched.size === 1 &&
    matchedFields.length === 1 &&
    matchedFields[0] === "description"
  ) {
    return null;
  }
  const tier = nameMatchTier(document.fieldTokens.name, queryTokens);
  let queryWeight = 0;
  for (const term of queryTokens) queryWeight += idf(term, corpus);
  let matchedWeight = 0;
  for (const term of queryTokens) if (matched.has(term)) matchedWeight += idf(term, corpus);
  const idfCoverage = queryWeight ? matchedWeight / queryWeight : 0.0;
  const nameTier = tier !== null ? tier : matched.size === queryTokens.length ? 3 : 4;
  const nonNamePhrase = FIELD_ORDER.some(
    (field) => field !== "name" && containsTokens(document.fieldTokens[field], queryTokens),
  );
  const phraseBonus = nonNamePhrase ? queryWeight * PHRASE_MULTIPLIER : 0.0;
  const nameBonus = tier !== null ? queryWeight * NAME_MATCH_MULTIPLIERS[tier] : 0.0;
  const retrievalScore = bm25fScore(document, queryTokens, corpus, prefixHits) + phraseBonus + nameBonus;
  const record = document.record;
  const completeness =
    ["publisher", "released", "modality"].filter((field) => present(record[field])).length +
    ["has_paper", "has_repo", "has_dataset"].filter((field) => record[field]).length;
  const name = String(record.name || "");
  return {
    key: [-retrievalScore, -idfCoverage, nameTier, -completeness, Array.from(name).length, casefold(name), String(record.key || "")],
    missing: queryTokens.filter((token) => !matched.has(token)),
  };
}

function compareKeys(a, b) {
  for (let index = 0; index < a.length; index += 1) {
    if (a[index] < b[index]) return -1;
    if (a[index] > b[index]) return 1;
  }
  return 0;
}

const corpusCache = new WeakMap();

// Every record sharing one query token is a candidate, as in QueryService,
// except a multi-word query's lone description-only token (issue #432);
// the ranking puts full matches and exact names first. Each result keeps the
// query words it lacks, so a surface can tell a full match from a partial
// candidate instead of calling both a match.
export function searchCatalogMatches(records, query) {
  const tokens = searchTokens(String(query || "").split(/\s+/).filter(Boolean).join(" "));
  // The word typed last stays last, since it is the one treated as a prefix.
  const queryTokens = [...new Set(tokens)];
  if (tokens.length) {
    const last = tokens[tokens.length - 1];
    queryTokens.splice(queryTokens.indexOf(last), 1);
    queryTokens.push(last);
  }
  if (!queryTokens.length) return [];
  let corpus = corpusCache.get(records);
  if (!corpus) {
    corpus = buildCorpus(records);
    corpusCache.set(records, corpus);
  }
  const scored = [];
  for (const document of corpus.documents) {
    const match = sortKey(document, queryTokens, corpus);
    if (match) scored.push({ ...match, record: document.record });
  }
  scored.sort((a, b) => compareKeys(a.key, b.key));
  return scored.map(({ record, missing }) => ({ record, missing }));
}

export function searchCatalog(records, query) {
  return searchCatalogMatches(records, query).map((match) => match.record);
}
