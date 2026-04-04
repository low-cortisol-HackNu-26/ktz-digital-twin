// Root layout — wraps the entire app.
//
// Responsibilities:
//   - Set <html lang="en" className="dark"> (HMI always starts dark)
//   - Import global CSS (globals.css)
//   - Wrap children in <Providers> (CardAuthProvider, QueryClientProvider, ThemeProvider)
//   - Include <Toaster> for alert notifications (shadcn/ui)
//   - Metadata: title "KTZ Digital Twin", viewport content="width=1920" (fixed HMI width)
