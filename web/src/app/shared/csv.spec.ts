import { describe, expect, it } from 'vitest';
import { fillTemplate, missingColumns, parseCsv } from './csv';

describe('parseCsv', () => {
  it('reads a header and its rows', () => {
    const table = parseCsv('name,email\nJane,jane@example.com\n');
    expect(table.columns).toEqual(['name', 'email']);
    expect(table.rows).toEqual([{ name: 'Jane', email: 'jane@example.com' }]);
  });

  it('accepts semicolons, which is what Czech and German Excel writes', () => {
    const table = parseCsv('name;email\nJana;jana@example.cz\n');
    expect(table.rows[0]).toEqual({ name: 'Jana', email: 'jana@example.cz' });
  });

  it('keeps a comma that sits inside a quoted field', () => {
    const table = parseCsv('name,note\n"Doe, Jane",bought twice\n');
    expect(table.rows[0]['name']).toBe('Doe, Jane');
  });

  it('reads a doubled quote as one quote', () => {
    const table = parseCsv('name\n"She said ""hi"""\n');
    expect(table.rows[0]['name']).toBe('She said "hi"');
  });

  it('keeps a newline inside a quoted field', () => {
    const table = parseCsv('name,note\nJane,"line one\nline two"\n');
    expect(table.rows[0]['note']).toBe('line one\nline two');
  });

  it('survives a byte order mark and CRLF', () => {
    const table = parseCsv('﻿name,email\r\nJane,jane@example.com\r\n');
    expect(table.columns[0]).toBe('name');
    expect(table.rows[0]['email']).toBe('jane@example.com');
  });

  it('keeps accents intact', () => {
    const table = parseCsv('name\nŠárka Melicharová\n');
    expect(table.rows[0]['name']).toBe('Šárka Melicharová');
  });

  it('drops blank lines rather than making empty buyers', () => {
    const table = parseCsv('name\nJane\n\n\nJohn\n');
    expect(table.rows).toHaveLength(2);
  });

  it('returns nothing for an empty file', () => {
    expect(parseCsv('')).toEqual({ columns: [], rows: [] });
  });
});

describe('fillTemplate', () => {
  it('fills placeholders from the row', () => {
    expect(fillTemplate('{name} <{email}>', { name: 'Jane', email: 'j@x.cz' })).toBe(
      'Jane <j@x.cz>',
    );
  });

  it('leaves an unknown placeholder visible rather than blank', () => {
    // A silently empty seal is worse than an obviously wrong one: it would be
    // written into every copy before anyone noticed.
    expect(fillTemplate('{name} {order}', { name: 'Jane' })).toBe('Jane {order}');
  });
});

describe('missingColumns', () => {
  it('names the placeholders the CSV cannot fill', () => {
    expect(missingColumns('{name} {order}', ['name', 'email'])).toEqual(['order']);
  });

  it('says nothing when every placeholder is covered', () => {
    expect(missingColumns('{name}', ['name'])).toEqual([]);
  });
});
