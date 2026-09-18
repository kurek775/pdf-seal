import { Component, inject, input, output, signal } from '@angular/core';
import { SealApi } from '../../core/seal-api';
import { UploadResult } from '../../core/types';
import { FileDrop } from '../../shared/file-drop/file-drop';

/** Step one: take the PDF and report what is in it that must survive. */
@Component({
  selector: 'app-upload-step',
  imports: [FileDrop],
  templateUrl: './upload-step.html',
})
export class UploadStep {
  readonly result = input<UploadResult | null>(null);
  readonly uploaded = output<UploadResult>();
  readonly cleared = output<void>();

  private readonly api = inject(SealApi);
  protected readonly busy = signal(false);
  protected readonly error = signal('');
  protected readonly filename = signal('');

  protected onPicked(file: File): void {
    this.error.set('');
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.error.set('That is not a PDF.');
      return;
    }
    this.busy.set(true);
    this.filename.set(file.name);
    this.api.upload(file).subscribe({
      next: (result) => {
        this.busy.set(false);
        this.uploaded.emit(result);
      },
      error: (err: Error) => {
        this.busy.set(false);
        this.error.set(err.message);
      },
    });
  }

  protected clear(): void {
    this.filename.set('');
    this.error.set('');
    this.cleared.emit();
  }
}
