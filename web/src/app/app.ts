import { Component, signal } from '@angular/core';
import { SealRow, UploadResult } from './core/types';
import { BuyersStep } from './features/buyers/buyers-step';
import { SealStep } from './features/seal/seal-step';
import { UploadStep } from './features/upload/upload-step';

/**
 * The shell holds the two things the steps share -- the uploaded file and the
 * list of buyers -- and nothing else. Each step owns its own state and reports
 * upwards, so a step can be changed without the others noticing.
 */
@Component({
  selector: 'app-root',
  imports: [UploadStep, BuyersStep, SealStep],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly upload = signal<UploadResult | null>(null);
  protected readonly rows = signal<SealRow[]>([]);

  protected onUploaded(result: UploadResult): void {
    this.upload.set(result);
  }

  protected onCleared(): void {
    this.upload.set(null);
  }

  protected onRows(rows: SealRow[]): void {
    this.rows.set(rows);
  }
}
