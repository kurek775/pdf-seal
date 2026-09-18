import { Component, ElementRef, input, output, signal, viewChild } from '@angular/core';

/**
 * A drop zone that is also a button, because dragging is not available to
 * everyone: it is focusable, reacts to Enter and Space, and opens the ordinary
 * file picker either way.
 */
@Component({
  selector: 'app-file-drop',
  templateUrl: './file-drop.html',
  styleUrl: './file-drop.css',
})
export class FileDrop {
  readonly accept = input('');
  readonly label = input('Drop a file here');
  readonly hint = input('');
  readonly picked = output<File>();

  protected readonly hovering = signal(false);
  private readonly picker = viewChild.required<ElementRef<HTMLInputElement>>('picker');

  protected open(): void {
    this.picker().nativeElement.click();
  }

  protected onKey(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      this.open();
    }
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.hovering.set(true);
  }

  protected onDragLeave(): void {
    this.hovering.set(false);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.hovering.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.picked.emit(file);
    }
  }

  protected onPick(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.picked.emit(file);
    }
    // Cleared so picking the same file twice in a row still fires a change.
    input.value = '';
  }
}
