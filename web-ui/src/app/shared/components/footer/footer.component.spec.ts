import { TestBed } from '@angular/core/testing';
import { FaIconLibrary } from '@fortawesome/angular-fontawesome';
import { FooterComponent } from './footer.component';
import { faGithub } from '@fortawesome/free-brands-svg-icons';

describe('FooterComponent', () => {
  let librarySpy: FaIconLibrary;

  beforeEach(() => {
    librarySpy = { addIcons: jest.fn() } as unknown as FaIconLibrary;
    TestBed.configureTestingModule({
      imports: [FooterComponent],
      providers: [{ provide: FaIconLibrary, useValue: librarySpy }],
    });
  });

  it('should create the component and add GitHub icon to library', () => {
    const fixture = TestBed.createComponent(FooterComponent);
    const component = fixture.componentInstance;
    expect(component).toBeTruthy();
    expect(librarySpy.addIcons as jest.Mock).toHaveBeenCalledWith(faGithub);
  });
});
