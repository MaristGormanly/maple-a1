// Initialise the Angular JIT compiler and the TestBed environment.
// This file is run once before every spec file via angular.json setupFile.
import '@angular/compiler';
import { getTestBed } from '@angular/core/testing';
import {
  BrowserTestingModule,
  platformBrowserTesting,
} from '@angular/platform-browser/testing';

getTestBed().initTestEnvironment(
  BrowserTestingModule,
  platformBrowserTesting(),
  { errorOnUnknownElements: true, errorOnUnknownProperties: true },
);
