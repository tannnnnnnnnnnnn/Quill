import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const extensionRoot = path.resolve(import.meta.dirname, "..");
const entryPoint = path.join(extensionRoot, "background.js");

function tokenize(source) {
  const tokens = [];
  let index = 0;
  let line = 1;
  let column = 1;

  function advance() {
    const character = source[index++];
    if (character === "\n") {
      line += 1;
      column = 1;
    } else {
      column += 1;
    }
    return character;
  }

  function add(type, value, tokenLine, tokenColumn) {
    tokens.push({ type, value, line: tokenLine, column: tokenColumn });
  }

  function regexCanStart() {
    const previous = tokens.at(-1);
    if (!previous) return true;
    return [
      "(", "[", "{", "=", ":", ",", ";", "!", "?", "&&", "||", "??",
      "=>", "return", "throw", "case", "delete", "typeof", "void", "yield"
    ].includes(previous.value);
  }

  while (index < source.length) {
    const character = source[index];
    if (/\s/.test(character)) {
      advance();
      continue;
    }

    if (character === "/" && source[index + 1] === "/") {
      while (index < source.length && advance() !== "\n") {}
      continue;
    }
    if (character === "/" && source[index + 1] === "*") {
      advance();
      advance();
      while (
        index < source.length &&
        !(source[index] === "*" && source[index + 1] === "/")
      ) {
        advance();
      }
      advance();
      advance();
      continue;
    }

    const tokenLine = line;
    const tokenColumn = column;
    if (character === "'" || character === '"') {
      const quote = advance();
      let value = "";
      while (index < source.length && source[index] !== quote) {
        if (source[index] === "\\") {
          advance();
          if (index < source.length) value += advance();
        } else {
          value += advance();
        }
      }
      assert.equal(
        source[index],
        quote,
        `Unterminated string at ${tokenLine}:${tokenColumn}`
      );
      advance();
      add("string", value, tokenLine, tokenColumn);
      continue;
    }

    if (character === "`") {
      advance();
      while (index < source.length) {
        if (source[index] === "\\") {
          advance();
          if (index < source.length) advance();
        } else if (source[index] === "`") {
          advance();
          break;
        } else {
          advance();
        }
      }
      assert.ok(
        index <= source.length && source[index - 1] === "`",
        `Unterminated template at ${tokenLine}:${tokenColumn}`
      );
      add("template", "", tokenLine, tokenColumn);
      continue;
    }

    if (character === "/" && regexCanStart()) {
      advance();
      let inCharacterClass = false;
      while (index < source.length) {
        if (source[index] === "\\") {
          advance();
          if (index < source.length) advance();
        } else if (source[index] === "[") {
          inCharacterClass = true;
          advance();
        } else if (source[index] === "]") {
          inCharacterClass = false;
          advance();
        } else if (source[index] === "/" && !inCharacterClass) {
          advance();
          while (/[a-z]/i.test(source[index] || "")) advance();
          break;
        } else {
          advance();
        }
      }
      add("regex", "", tokenLine, tokenColumn);
      continue;
    }

    if (/[A-Za-z_$]/.test(character)) {
      let value = "";
      while (/[A-Za-z0-9_$]/.test(source[index] || "")) value += advance();
      add("identifier", value, tokenLine, tokenColumn);
      continue;
    }

    if (/[0-9]/.test(character)) {
      let value = "";
      while (/[A-Za-z0-9_.]/.test(source[index] || "")) value += advance();
      add("number", value, tokenLine, tokenColumn);
      continue;
    }

    const punctuator = ["=>", "===", "!==", "&&", "||", "??", "?.", "**"]
      .find((candidate) => source.startsWith(candidate, index));
    if (punctuator) {
      for (let offset = 0; offset < punctuator.length; offset += 1) advance();
      add("punctuator", punctuator, tokenLine, tokenColumn);
    } else {
      add("punctuator", advance(), tokenLine, tokenColumn);
    }
  }

  return tokens;
}

function parseModule(source, filename) {
  const tokens = tokenize(source);
  const imports = [];

  for (let index = 0; index < tokens.length; index += 1) {
    if (tokens[index].value !== "import" && tokens[index].value !== "export") {
      continue;
    }
    if (tokens[index].value === "import" && tokens[index + 1]?.value === "(") {
      continue;
    }
    for (let cursor = index + 1; cursor < tokens.length; cursor += 1) {
      if (tokens[cursor].value === ";") break;
      if (tokens[cursor].type === "string") {
        imports.push(tokens[cursor].value);
        break;
      }
    }
  }

  const matchingParen = new Map();
  const parenStack = [];
  for (let index = 0; index < tokens.length; index += 1) {
    if (tokens[index].value === "(") parenStack.push(index);
    if (tokens[index].value === ")") {
      const opening = parenStack.pop();
      assert.notEqual(opening, undefined, `Unmatched ) in ${filename}`);
      matchingParen.set(index, opening);
    }
  }
  assert.equal(parenStack.length, 0, `Unmatched ( in ${filename}`);

  const functionBodies = new Set();
  const controlWords = new Set(["if", "for", "while", "switch", "catch", "with"]);
  for (let index = 0; index < tokens.length; index += 1) {
    if (tokens[index].value === "function") {
      const body = tokens.findIndex(
        (token, candidate) => candidate > index && token.value === "{"
      );
      assert.notEqual(body, -1, `Function without a body in ${filename}`);
      functionBodies.add(body);
    }
    if (tokens[index].value === "=>" && tokens[index + 1]?.value === "{") {
      functionBodies.add(index + 1);
    }
    if (tokens[index].value === "{" && tokens[index - 1]?.value === ")") {
      const openingParen = matchingParen.get(index - 1);
      const beforeParen = tokens[openingParen - 1]?.value;
      if (!controlWords.has(beforeParen)) functionBodies.add(index);
    }
  }

  const scopes = [];
  let functionDepth = 0;
  const topLevelAwaits = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token.value === "await" && functionDepth === 0) {
      topLevelAwaits.push(`${filename}:${token.line}:${token.column}`);
    }
    if (token.value === "{") {
      const isFunction = functionBodies.has(index);
      scopes.push(isFunction);
      if (isFunction) functionDepth += 1;
    } else if (token.value === "}") {
      const wasFunction = scopes.pop();
      assert.notEqual(wasFunction, undefined, `Unmatched } in ${filename}`);
      if (wasFunction) functionDepth -= 1;
    }
  }
  assert.equal(scopes.length, 0, `Unmatched { in ${filename}`);

  return { imports, topLevelAwaits };
}

assert.equal(
  parseModule("await initialize();", "top-level-await.js").topLevelAwaits.length,
  1
);
assert.equal(
  parseModule(
    "for await (const item of items) { consume(item); }",
    "top-level-for-await.js"
  ).topLevelAwaits.length,
  1
);
assert.deepEqual(
  parseModule(
    "async function initialize() { await load(); }",
    "function-await.js"
  ).topLevelAwaits,
  []
);

const visited = new Set();
const topLevelAwaits = [];

async function inspectModule(filename) {
  const canonical = path.resolve(filename);
  if (visited.has(canonical)) return;
  visited.add(canonical);

  const source = await readFile(canonical, "utf8");
  const parsed = parseModule(source, path.relative(extensionRoot, canonical));
  topLevelAwaits.push(...parsed.topLevelAwaits);

  for (const specifier of parsed.imports) {
    if (!specifier.startsWith(".") && !specifier.startsWith("/")) continue;
    const imported = fileURLToPath(
      new URL(specifier, pathToFileURL(canonical))
    );
    await inspectModule(imported);
  }
}

await inspectModule(entryPoint);
assert.deepEqual(
  topLevelAwaits,
  [],
  `Service-worker modules contain top-level await:\n${topLevelAwaits.join("\n")}`
);

const modules = [...visited]
  .map((filename) => path.relative(extensionRoot, filename))
  .sort();
console.log(
  `PASS service-worker module graph has no top-level await: ${modules.join(", ")}`
);
