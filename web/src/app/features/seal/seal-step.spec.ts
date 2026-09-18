import { provideZonelessChangeDetection } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { beforeEach, describe, expect, it } from 'vitest';
import { SealStep } from './seal-step';
import { UploadResult } from '../../core/types';

const upload: UploadResult = {
  id: 'a'.repeat(32),
  pages: 6,
  counts: { links: 62, jumps: 139, web: 0, bookmarks: 78 },
};

describe('SealStep', () => {
  let fixture: ComponentFixture<SealStep>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SealStep],
      providers: [provideZonelessChangeDetection(), provideHttpClient()],
    }).compileComponents();

    fixture = TestBed.createComponent(SealStep);
    fixture.componentRef.setInput('upload', upload);
    fixture.componentRef.setInput('rows', [{ text: 'Jane', filename: 'jane.pdf' }]);
    await fixture.whenStable();
  });

  it('offers to seal once there is someone to seal for', () => {
    expect(fixture.nativeElement.textContent).toContain('Seal 1 copy');
  });

  it('does not say "Seal 0 copies" when there is nobody yet', async () => {
    fixture.componentRef.setInput('rows', []);
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).not.toContain('Seal 0');
  });

  it('forgets a finished download once the buyers change', async () => {
    // Otherwise the confirmation from the previous run stays on screen and
    // claims a file was saved for buyers nobody has sealed for yet.
    const component = fixture.componentInstance as unknown as {
      finished: { set: (value: unknown) => void };
    };
    component.finished.set({ blob: new Blob(), filename: 'jane.pdf' });
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).toContain('has been saved');

    fixture.componentRef.setInput('rows', [{ text: 'John', filename: 'john.pdf' }]);
    await fixture.whenStable();
    expect(fixture.nativeElement.textContent).not.toContain('has been saved');
  });
});
