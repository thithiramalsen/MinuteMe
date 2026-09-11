import { SignIn } from "@clerk/clerk-react";

// This object configures the Clerk component to match your app's theme
const clerkAppearance = {
  variables: {
    colorPrimary: "#3b82f6", // Your --accent-color
    colorBackground: "#1f2937", // Your --primary-dark
    colorInputBackground: "#111827", // Your --background-dark
    colorText: "#f9fafb", // Your --text-primary
    colorTextSecondary: "#9ca3af", // Your --text-secondary
    colorInputText: "#f9fafb",
  },
  elements: {
    card: {
      backgroundColor: "var(--primary-dark)",
      border: "1px solid var(--border-color)",
      boxShadow: "0 8px 32px rgba(0, 0, 0, 0.2)",
    },
    socialButtonsBlockButton: {
      borderColor: "var(--border-color)",
      "&:hover": {
        backgroundColor: "#374151",
      },
    },
    footerActionLink: {
      color: "var(--accent-color)",
      "&:hover": {
        color: "#60a5fa",
      },
    },
  },
};

export default function SignInPage() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <SignIn 
        path="/sign-in" 
        routing="path" 
        signUpUrl="/sign-up"
        appearance={clerkAppearance}
      />
    </div>
  );
}