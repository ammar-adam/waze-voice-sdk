// What a suggested name may contain before it is shown to every visitor.
// Used by api/suggestions.js. The leading underscore keeps Vercel from
// turning this file into a function.
//
// Three checks, cheapest first:
//   1. Shape. NFKC folds fullwidth and "mathematical" letters to plain ones;
//      then only letters, ASCII digits, spaces and ' ’ . & ! - are allowed,
//      so zero-width characters, bidi overrides, emoji and combining-mark
//      pile-ups are refused.
//   2. One alphabet. A name mixing scripts (a Cyrillic "о" in "Yоda") is
//      a lookalike trick: it dodges the word list below and shows up as a
//      twin of a real entry. Chinese, Japanese and Korean may mix with each
//      other; nothing else mixes.
//   3. A short word list. Slurs and sexual terms, matched after folding
//      l33t-speak, lookalike letters and stretched letters ("fuuuck").
//      Deliberately small: it catches the obvious, and the owner removes the
//      rest (see api/suggestions.js for how). Words that are also parts of
//      real character names (Dick Grayson, Moby Dick, Cockatoo, Raccoon,
//      Grape Ape, Benedict Cumberbatch) are matched as whole words only.

// Matched anywhere in the name, letters only, spaces removed.
const ANYWHERE = [
  'niger', 'niga', 'nigr', 'fagot', 'kike', 'trany', 'retard', 'cunt', 'fuck', 'shit', 'whore',
  'slut', 'bitch', 'asshole', 'motherfuck', 'twat', 'wank', 'jizz', 'dildo', 'porn', 'hentai',
  'penis', 'vagina', 'hitler', 'nazi', 'rapist', 'molest', 'wetback', 'beaner', 'milf', 'cumshot',
];
// Matched as whole words only.
const WORDS = [
  'fag', 'fags', 'rape', 'raped', 'raping', 'rapes', 'cock', 'cocks', 'pussy', 'pussies', 'cum', 'sex',
  'sexy', 'anal', 'anus', 'tits', 'titties', 'boob', 'boobs', 'nude', 'nudes', 'naked', 'spic',
  'spics', 'chink', 'chinks', 'gook', 'gooks', 'coon', 'coons', 'dyke', 'dykes', 'pedo', 'pedos',
  'paedo', 'kkk', 'jihad','blowjob', 'handjob', 'orgasm', 'horny', 'semen',
];

// l33t and lookalikes, folded to the letter they pretend to be. Cyrillic and
// Greek twins are here too, so an all-Cyrillic spelling of a slur still hits.
const FOLD = {
  0: 'o', 1: 'i', 3: 'e', 4: 'a', 5: 's', 7: 't', 8: 'b', 9: 'g', '@': 'a', $: 's', '!': 'i', '|': 'i',
  а: 'a', в: 'b', е: 'e', ё: 'e', к: 'k', м: 'm', н: 'h', о: 'o', р: 'p', с: 'c', т: 't', у: 'y', х: 'x',
  і: 'i', ї: 'i', ј: 'j', ѕ: 's', ԁ: 'd', ɡ: 'g', һ: 'h', ո: 'n', ս: 'u',
  α: 'a', β: 'b', ε: 'e', η: 'n', ι: 'i', κ: 'k', ν: 'v', ο: 'o', ρ: 'p', τ: 't', υ: 'u', χ: 'x',
};

const SCRIPTS = [
  ['latin', /\p{Script=Latin}/u], ['cyrillic', /\p{Script=Cyrillic}/u], ['greek', /\p{Script=Greek}/u],
  ['arabic', /\p{Script=Arabic}/u], ['hebrew', /\p{Script=Hebrew}/u], ['thai', /\p{Script=Thai}/u],
  ['devanagari', /\p{Script=Devanagari}/u],
  ['cjk', /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}ー々]/u],
];

// Blank-looking "letters" used to post invisible names.
const INVISIBLE = /[ᅟᅠㅤﾠ⠀឴឵]/u;

function scriptOf(ch) {
  for (const [name, re] of SCRIPTS) if (re.test(ch)) return name;
  return null;
}

// The name folded for the word lists: lower case, no accents, l33t and
// lookalikes undone, anything that is not a letter turned into a space.
function folded(name) {
  return [...String(name).normalize('NFKD').replace(/\p{M}+/gu, '').toLowerCase()]
    .map((c) => (Object.prototype.hasOwnProperty.call(FOLD, c) ? FOLD[c] : c))
    .join('')
    .replace(/[^a-z]+/g, ' ')
    .trim();
}

// Runs of one letter squeezed to one: "fuuuck" -> "fuck", "faggot" -> "fagot".
const squeeze = (w) => w.replace(/([a-z])\1+/g, '$1');
const WORD_SET = new Set(WORDS);
const ANYWHERE_SQUEEZED = ANYWHERE.map(squeeze);

// Is it offensive? ANYWHERE is compared squeezed on both sides. WORDS are
// compared as typed and squeezed, so "Bob" is never mistaken for "boob"
// (the price: "boooobs" squeezes to "bobs" and gets through).
function offensive(name) {
  const text = folded(name);
  const joined = text.replace(/ /g, '');
  if (ANYWHERE_SQUEEZED.some((w) => squeeze(joined).includes(w))) return true;
  let words = text.split(' ').filter(Boolean);
  // "c o c k" spelled out a letter at a time.
  if (words.length > 2 && words.every((w) => w.length === 1)) words = [joined];
  return words.some((w) => WORD_SET.has(w) || WORD_SET.has(squeeze(w)));
}

// A name fit to show, or an error for the person typing it.
function clean(raw) {
  if (typeof raw !== 'string' || raw.length > 200) return {error: 'Names are 2 to 40 characters.'};
  const name = raw.normalize('NFKC').replace(/\s+/g, ' ').trim();
  if (name.length < 2 || name.length > 40) return {error: 'Names are 2 to 40 characters.'};
  if (/https?:|www\.|\.(com|net|org|io|gg|app|xyz|tv)\b|[<>{}@]/i.test(name)) {
    return {error: 'Just the character\'s name, please.'};
  }
  if (INVISIBLE.test(name) || !/^[\p{L}0-9 '’.&!-]+$/u.test(name)) return {error: 'Letters, numbers and spaces only.'};
  const letters = name.match(/\p{L}/gu) || [];
  if (letters.length < 2) return {error: 'Letters, numbers and spaces only.'};
  const scripts = new Set(letters.map(scriptOf));
  if (scripts.has(null) || scripts.size > 1) return {error: 'One alphabet per name, please.'};
  if (offensive(name)) return {error: 'Let\'s keep it friendly. Try another name.'};
  return {name};
}

module.exports = {clean, offensive, folded};
