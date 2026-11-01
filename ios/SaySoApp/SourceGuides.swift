import SwiftUI

/// Step-by-step help for getting the user's own writing out of each app: chats, emails, essays.
struct SourceGuide: Identifiable {
    let name: String
    let systemImage: String
    let steps: [String]
    var note: String? = nil

    var id: String { name }

    static let chats: [SourceGuide] = [
        SourceGuide(name: "WhatsApp", systemImage: "phone.bubble", steps: [
            "Open the chat.",
            "Tap the contact's name at the top.",
            "Scroll down → Export Chat → Without Media.",
            "Save to Files, then come back and tap Add chat exports.",
        ]),
        SourceGuide(name: "Telegram", systemImage: "paperplane", steps: [
            "Telegram on a computer: open the chat → ⋮ → Export chat history.",
            "Format HTML, turn off photos and videos → Export.",
            "Send the folder (zipped) to your iPhone (AirDrop or Files), then tap Add chat exports.",
        ], note: "Only on a phone? Use a screen recording or screenshots below."),
        SourceGuide(name: "Instagram", systemImage: "camera", steps: [
            "Profile → ☰ → Accounts Center → Your information and permissions.",
            "Download your information → Some of your information → Messages.",
            "Download to device, format JSON → Create files.",
            "When Instagram emails you (minutes to hours), download the .zip and tap Add chat exports.",
        ]),
        SourceGuide(name: "iMessage and any other app", systemImage: "record.circle", steps: [
            "Control Center → Screen Recording, open the chat and scroll up slowly for a minute.",
            "Stop the recording, then tap Add screenshots or a screen recording.",
            "Or take a few screenshots of the chat instead.",
        ], note: "Your messages are the bubbles on the right; SaySo keeps only those."),
    ]

    static let emails: [SourceGuide] = [
        SourceGuide(name: "Screenshots (easiest)", systemImage: "camera.viewfinder", steps: [
            "In your mail app open Sent.",
            "Open an email you wrote; take screenshots (scroll for a long one).",
            "Repeat for 3–5 emails, then tap Add screenshots or photos.",
        ], note: "SaySo reads only what you wrote: no headers, no quoted replies from others."),
        SourceGuide(name: "Copy and paste", systemImage: "doc.on.clipboard", steps: [
            "Sent → open your email → touch and hold the text → Select All → Copy.",
            "Tap Paste text here and paste. Add a blank line between emails.",
        ]),
        SourceGuide(name: "Gmail as PDF", systemImage: "doc.richtext", steps: [
            "Open the email → ⋯ (top right) → Print.",
            "Tap Share (square with an arrow) → Save to Files.",
            "Tap Add files and pick the PDFs.",
        ]),
        SourceGuide(name: "Apple Mail as PDF", systemImage: "envelope", steps: [
            "Open the email → reply arrow ↩ → Print.",
            "Tap Share → Save to Files, then Add files.",
        ]),
        SourceGuide(name: "Many at once (computer)", systemImage: "tray.full", steps: [
            "takeout.google.com → Deselect all → select Mail.",
            "All Mail data included → keep only the Sent label → Export (.mbox).",
            "Put the .mbox on your iPhone and tap Add files (up to 20 MB).",
        ]),
    ]

    static let essays: [SourceGuide] = [
        SourceGuide(name: "Photos of pages", systemImage: "camera", steps: [
            "Photograph each page straight on, in good light (printed or handwritten).",
            "Tap Add screenshots or photos and pick them in order.",
        ]),
        SourceGuide(name: "Word, Pages, Google Docs", systemImage: "doc.text", steps: [
            "Google Docs: ⋯ → Share & export → Save as Word (.docx) → Save to Files.",
            "Pages: Share → Export → PDF or Word.",
            "Tap Add files and pick them (.docx, .pdf, .txt).",
        ]),
        SourceGuide(name: "Copy and paste", systemImage: "doc.on.clipboard", steps: [
            "Select the text anywhere → Copy, then tap Paste text here.",
        ]),
    ]
}

struct SourceGuideList: View {
    let guides: [SourceGuide]

    var body: some View {
        ForEach(guides) { guide in
            DisclosureGroup {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(Array(guide.steps.enumerated()), id: \.offset) { index, step in
                        HStack(alignment: .top, spacing: 8) {
                            Text("\(index + 1)").font(.caption.weight(.bold)).foregroundStyle(.white)
                                .frame(width: 18, height: 18).background(Color.accentColor, in: .circle)
                            Text(step).font(.subheadline)
                        }
                    }
                    if let note = guide.note {
                        Text(note).font(.footnote).foregroundStyle(.secondary)
                    }
                }
                .padding(.vertical, 4)
            } label: {
                Label(guide.name, systemImage: guide.systemImage)
            }
        }
    }
}
