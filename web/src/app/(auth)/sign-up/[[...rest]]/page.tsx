import { SignUp } from "@clerk/nextjs";

export default function Page() {
  return (
    <div className="relative z-10 min-h-dvh flex flex-col items-center justify-center px-4 py-16 bg-surface-deep text-ink">
      <div className="w-full max-w-md mb-10 text-center">
        <p className="font-display text-2xl tracking-tight mb-2">Create your account</p>
        <p className="text-sm text-ink-muted leading-relaxed">
          We sync your profile to the digest database on first dashboard visit—then the daily job can target your interests.
        </p>
      </div>
      <div className="w-full flex justify-center">
        <SignUp
          routing="path"
          path="/sign-up"
          appearance={{
            variables: {
              colorPrimary: "#c9a227",
              colorBackground: "#141210",
              colorInputBackground: "#1c1a17",
              colorText: "#e8e4dc",
              colorTextSecondary: "#9a948a",
              colorNeutral: "#6b665c",
              borderRadius: "0.375rem",
            },
            elements: {
              card: "shadow-none border border-[rgba(232,228,220,0.09)] bg-[#141210]",
              headerTitle: "font-display text-xl",
              socialButtonsBlockButton: "border-[rgba(232,228,220,0.12)]",
              formButtonPrimary: "shadow-none font-semibold",
            },
          }}
        />
      </div>
    </div>
  );
}
