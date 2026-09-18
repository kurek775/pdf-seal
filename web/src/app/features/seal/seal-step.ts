import { Component, computed, inject, input, output, signal } from '@angular/core';
import { SealApi, SealedFile } from '../../core/seal-api';
import { NavigationCounts, SealRow, UploadResult } from '../../core/types';

/** Step three: the options, the run, and the proof that nothing was lost. */
@Component({
  selector: 'app-seal-step',
  templateUrl: './seal-step.html',
})
export class SealStep {
  readonly upload = input.required<UploadResult>();
  readonly rows = input.required<SealRow[]>();
  readonly done = output<void>();

  private readonly api = inject(SealApi);
  protected readonly visible = signal(false);
  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly finished = signal<SealedFile | null>(null);

  protected readonly ready = computed(() => this.rows().length > 0);
  protected readonly counts = computed<NavigationCounts>(() => this.upload().counts);
  protected readonly hasNavigation = computed(
    () => this.counts().links > 0 || this.counts().bookmarks > 0,
  );

  protected run(): void {
    this.error.set('');
    this.finished.set(null);
    this.busy.set(true);
    this.api.seal({ id: this.upload().id, visible: this.visible(), rows: this.rows() }).subscribe({
      next: (file) => {
        this.busy.set(false);
        this.finished.set(file);
        this.save(file);
        this.done.emit();
      },
      error: (err: Error) => {
        this.busy.set(false);
        this.error.set(err.message);
      },
    });
  }

  /** Saves the result, and can be called again from the button if it was missed. */
  protected save(file: SealedFile | null = this.finished()): void {
    if (!file) {
      return;
    }
    const url = URL.createObjectURL(file.blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = file.filename;
    link.click();
    URL.revokeObjectURL(url);
  }
}
