import { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Helix — AI News Curator & Technical Intelligence",
    short_name: "Helix Curator",
    description:
      "Autonomous AI news curator and technical intelligence platform. Digests, ranks, and serves high-signal morning dossiers.",
    start_url: "/",
    display: "standalone",
    background_color: "#0d0c0a",
    theme_color: "#0d0c0a",
    icons: [
      {
        src: "/logo.png",
        sizes: "512x512",
        type: "image/png",
      },
      {
        src: "/favicon.ico",
        sizes: "48x48",
        type: "image/x-icon",
      },
    ],
  };
}
