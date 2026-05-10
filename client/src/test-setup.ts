// Initialise the Angular JIT compiler and the TestBed environment.
// This file is run once before every spec file via angular.json setupFiles.
import '@angular/compiler';
import { getTestBed } from '@angular/core/testing';
import {
  BrowserTestingModule,
  platformBrowserTesting,
} from '@angular/platform-browser/testing';

try {
  getTestBed().initTestEnvironment(
    BrowserTestingModule,
    platformBrowserTesting(),
    { errorOnUnknownElements: true, errorOnUnknownProperties: true },
  );
} catch (error) {
  if (!(error instanceof Error) || !error.message.includes('already been called')) {
    throw error;
  }
}
