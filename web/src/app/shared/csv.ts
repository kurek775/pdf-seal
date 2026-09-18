/**
 * A small CSV reader, written out rather than pulled in as a dependency.
 *
 * It handles what a spreadsheet actually exports: quoted fields, commas and
 * newlines inside quotes, doubled quotes as an escape, semicolon separators
 * (what Czech and German Excel writes), and a leading byte order mark.
 */

export interface CsvTable {
  columns: string[];
  rows: Record<string, string>[];
}

export function parseCsv(text: string): CsvTable {
  const clean = text.replace(/^﻿/, '').replace(/\r\n?/g, '\n');
  const separator = chooseSeparator(clean);
  const grid = toGrid(clean, separator).filter((row) => row.some((cell) => cell !== ''));
  if (grid.length === 0) {
    return { columns: [], rows: [] };
  }

  const columns = grid[0].map((name, index) => name.trim() || `column${index + 1}`);
  const rows = grid.slice(1).map((cells) => {
    const row: Record<string, string> = {};
    columns.forEach((name, index) => (row[name] = (cells[index] ?? '').trim()));
    return row;
  });
  return { columns, rows };
}

/** Whichever of comma or semicolon appears more often outside quotes wins. */
function chooseSeparator(text: string): string {
  const firstLine = toGrid(text, ',')[0] ?? [];
  return firstLine.length > 1 ? ',' : ';';
}

function toGrid(text: string, separator: string): string[][] {
  const grid: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let quoted = false;

  for (let i = 0; i < text.length; i++) {
    const character = text[i];
    if (quoted) {
      if (character === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i++;
        } else {
          quoted = false;
        }
      } else {
        cell += character;
      }
      continue;
    }
    if (character === '"') {
      quoted = true;
    } else if (character === separator) {
      row.push(cell);
      cell = '';
    } else if (character === '\n') {
      row.push(cell);
      grid.push(row);
      row = [];
      cell = '';
    } else {
      cell += character;
    }
  }
  row.push(cell);
  grid.push(row);
  return grid;
}

/** Fills `{column}` placeholders from a row; unknown names are left visible. */
export function fillTemplate(template: string, row: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => row[name] ?? whole);
}

/** Which placeholders a template asks for that the CSV does not have. */
export function missingColumns(template: string, columns: string[]): string[] {
  const asked = [...template.matchAll(/\{(\w+)\}/g)].map((match) => match[1]);
  return [...new Set(asked.filter((name) => !columns.includes(name)))];
}
