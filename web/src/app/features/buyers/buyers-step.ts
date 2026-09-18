import { Component, computed, effect, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SealRow } from '../../core/types';
import { fillTemplate, missingColumns, parseCsv } from '../../shared/csv';
import { FileDrop } from '../../shared/file-drop/file-drop';

type Mode = 'one' | 'many';

/**
 * Step two: who the copies are for.
 *
 * The seal text is shown exactly as it will be written, for every row, before
 * anything is sealed. Getting a name wrong across eighty files is expensive, and
 * a preview is the cheapest way to catch it.
 */
@Component({
  selector: 'app-buyers-step',
  imports: [FormsModule, FileDrop],
  templateUrl: './buyers-step.html',
})
export class BuyersStep {
  readonly rowsChanged = output<SealRow[]>();

  protected readonly mode = signal<Mode>('one');

  // One buyer
  protected readonly name = signal('');
  protected readonly email = signal('');
  protected readonly order = signal('');

  // Many buyers
  protected readonly csvName = signal('');
  protected readonly columns = signal<string[]>([]);
  protected readonly csvRows = signal<Record<string, string>[]>([]);
  protected readonly template = signal('{name} | {email} | order {order}');
  protected readonly filenameTemplate = signal('{email}.pdf');
  protected readonly csvError = signal('');

  protected readonly unknownPlaceholders = computed(() =>
    missingColumns(this.template() + this.filenameTemplate(), this.columns()),
  );

  protected readonly rows = computed<SealRow[]>(() => {
    if (this.mode() === 'one') {
      const text = [this.name(), this.email(), this.order() && `order ${this.order()}`]
        .filter(Boolean)
        .join(' | ');
      if (!text) {
        return [];
      }
      const base = this.email() || this.name() || 'sealed';
      return [{ text, filename: `${base}.pdf` }];
    }
    return this.csvRows().map((row) => ({
      text: fillTemplate(this.template(), row),
      filename: fillTemplate(this.filenameTemplate(), row),
    }));
  });

  protected readonly preview = computed(() => this.rows().slice(0, 5));

  constructor() {
    // The parent only needs the finished list, so it is pushed whenever the
    // computed changes. An effect is the right tool here: it is tied to the
    // component's lifetime and runs only when something it reads actually moved.
    effect(() => this.rowsChanged.emit(this.rows()));
  }

  protected setMode(mode: Mode): void {
    this.mode.set(mode);
  }

  protected onCsv(file: File): void {
    this.csvError.set('');
    file
      .text()
      .then((text) => {
        const table = parseCsv(text);
        if (table.rows.length === 0) {
          this.csvError.set('That CSV has no rows.');
          return;
        }
        this.csvName.set(file.name);
        this.columns.set(table.columns);
        this.csvRows.set(table.rows);
      })
      .catch(() => this.csvError.set('That file could not be read.'));
  }
}
