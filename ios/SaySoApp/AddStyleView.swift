import AVFoundation
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

/// Adding a style: name it, add chats (exports, screenshots, a screen recording), say which participant is you,
/// then watch it learn and check itself.
struct AddStyleView: View {
    let onUse: (Style) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var files: [Upload] = []
    @State private var picked: [PhotosPickerItem] = []
    @State private var importing = false
    @State private var preparing = false
    @State private var style: Style?
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Group {
                if let style {
                    BuildProgressView(style: style, onUse: onUse) { self.style = $0 }
                } else {
                    form
                }
            }
            .navigationTitle(style?.name ?? "New style")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(style == nil ? "Cancel" : "Close") { dismiss() } }
            }
        }
    }

    private var form: some View {
        Form {
            Section("Name") {
                TextField("e.g. Me with friends, Work me", text: $name)
            }
            Section {
                Button { importing = true } label: { Label("Add chat exports", systemImage: "doc.badge.plus") }
                PhotosPicker(selection: $picked, matching: .any(of: [.screenshots, .images, .videos])) {
                    Label("Add screenshots or a screen recording", systemImage: "photo.on.rectangle.angled")
                }
                ForEach(Array(files.enumerated()), id: \.offset) { index, file in
                    HStack {
                        Image(systemName: icon(file)).foregroundStyle(.secondary)
                        Text(file.name).lineLimit(1)
                        Spacer()
                        Text(ByteCountFormatter.string(fromByteCount: Int64(file.data.count), countStyle: .file))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    .swipeActions { Button("Remove", role: .destructive) { files.remove(at: index) } }
                }
                if preparing { ProgressView("Preparing…") }
            } header: {
                Text("Chats")
            } footer: {
                Text("""
                WhatsApp: open a chat → ⋯ → Export Chat → Without Media → Save to Files.
                Telegram: Telegram Desktop → Export chat history (HTML).
                Instagram: Accounts Center → Download your information → Messages, JSON.
                Anything else (iMessage too): screenshots, or a screen recording while you scroll up a chat.
                Only your own messages are kept; the other side is read once to learn how you react, then dropped.
                """)
            }
            if let error {
                Section { Text(error).foregroundStyle(.red) }
            }
            Section {
                Button {
                    Task { await create() }
                } label: {
                    Text("Create style").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(files.isEmpty || preparing)
            }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.zip, .plainText, .json, .html],
                      allowsMultipleSelection: true) { result in
            if case .success(let urls) = result { add(urls) }
        }
        .onChange(of: picked) { _, items in
            guard !items.isEmpty else { return }
            Task { await addMedia(items) }
        }
    }

    private func icon(_ file: Upload) -> String {
        file.mimeType.hasPrefix("image") ? "photo" : "doc.text"
    }

    private func add(_ urls: [URL]) {
        for url in urls {
            let scoped = url.startAccessingSecurityScopedResource()
            defer { if scoped { url.stopAccessingSecurityScopedResource() } }
            if let data = try? Data(contentsOf: url) {
                let type = UTType(filenameExtension: url.pathExtension)?.preferredMIMEType ?? "application/octet-stream"
                files.append(Upload(name: url.lastPathComponent, data: data, mimeType: type))
            }
        }
    }

    /// Screenshots go up as JPEG; a screen recording becomes a frame every 1.5 s (up to 60), read like screenshots.
    private func addMedia(_ items: [PhotosPickerItem]) async {
        preparing = true
        defer { preparing = false; picked = [] }
        for (index, item) in items.enumerated() {
            if item.supportedContentTypes.contains(where: { $0.conforms(to: .movie) }) {
                guard let movie = try? await item.loadTransferable(type: Movie.self) else { continue }
                let frames = await Self.frames(of: movie.url)
                for (n, frame) in frames.enumerated() {
                    files.append(Upload(name: String(format: "recording%02d-%03d.jpg", index, n), data: frame, mimeType: "image/jpeg"))
                }
                try? FileManager.default.removeItem(at: movie.url)
            } else if let data = try? await item.loadTransferable(type: Data.self) {
                files.append(Upload(name: String(format: "screenshot%03d.jpg", index), data: SaySoAPI.jpeg(data), mimeType: "image/jpeg"))
            }
        }
    }

    static func frames(of url: URL, every step: Double = 1.5, limit: Int = 60) async -> [Data] {
        let asset = AVURLAsset(url: url)
        guard let duration = try? await asset.load(.duration) else { return [] }
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = CMTime(seconds: 0.3, preferredTimescale: 600)
        var frames: [Data] = []
        var second = 0.5
        while second < duration.seconds && frames.count < limit {
            if let image = try? await generator.image(at: CMTime(seconds: second, preferredTimescale: 600)).image,
               let jpeg = SaySoAPI.jpeg(UIImage(cgImage: image)) {
                frames.append(jpeg)
            }
            second += step
        }
        return frames
    }

    private func create() async {
        preparing = true
        defer { preparing = false }
        do {
            style = try await SaySoAPI.createStyle(name: name.isEmpty ? "My style" : name, files: files)
            files = []
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// A screen recording from Photos, copied to a temporary file.
struct Movie: Transferable {
    let url: URL

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .movie) { SentTransferredFile($0.url) } importing: { received in
            let copy = FileManager.default.temporaryDirectory.appending(path: "\(UUID().uuidString).\(received.file.pathExtension)")
            try FileManager.default.copyItem(at: received.file, to: copy)
            return Movie(url: copy)
        }
    }
}

/// Stages of a style being built, the "Which one is you?" step, and the self-check at the end.
struct BuildProgressView: View {
    let style: Style
    let onUse: (Style) -> Void
    let onChange: (Style) -> Void

    @State private var me = ""
    @State private var chats: [String: String] = [:]
    @State private var sending = false
    @State private var error: String?

    var body: some View {
        Form {
            if style.stage == "needs_me" {
                whoIsWho
            } else if style.status == "failed" {
                Section { Label(style.error ?? "Couldn't build this style.", systemImage: "exclamationmark.triangle").foregroundStyle(.red) }
            } else {
                Section("Learning your style") {
                    ForEach(StageInfo.order.filter { $0 != "needs_me" && ($0 != "training" || style.lora == "training") }, id: \.self) { stage in
                        StageRow(title: StageInfo.title(stage), state: state(of: stage))
                    }
                    if style.isBuilding { ProgressView(value: style.progress ?? 0) }
                }
            }
            if let scores = style.scores, style.isReady {
                SelfCheckSection(scores: scores, lora: style.lora)
                Section {
                    Button { onUse(style) } label: { Text("Use this style").frame(maxWidth: .infinity) }
                        .buttonStyle(.borderedProminent)
                }
            }
            if let error { Section { Text(error).foregroundStyle(.red) } }
        }
        .task(id: style.id) { await poll() }
        .onAppear {
            me = style.me ?? style.participants?.first ?? ""
            chats = style.chats ?? [:]
        }
        .onChange(of: style.stage) { _, _ in
            if me.isEmpty { me = style.me ?? style.participants?.first ?? "" }
            if chats.isEmpty { chats = style.chats ?? [:] }
        }
    }

    @ViewBuilder private var whoIsWho: some View {
        if style.needs?.contains("me") == true {
            Section {
                Picker("Which one is you?", selection: $me) {
                    ForEach(style.participants ?? [], id: \.self) { Text($0).tag($0) }
                }
                .pickerStyle(.inline)
                .labelsHidden()
            } header: {
                Text("Which one is you?")
            }
        }
        Section {
            ForEach(chats.keys.sorted(), id: \.self) { chat in
                Picker(chat, selection: Binding(get: { chats[chat] ?? "friends" }, set: { chats[chat] = $0 })) {
                    ForEach(Audience.allCases) { Text($0.label).tag($0.rawValue) }
                }
            }
        } header: {
            Text("Who are these chats with?")
        } footer: {
            Text("SaySo guessed; fix anything that's wrong. It learns how you write to each kind of person.")
        }
        Section {
            Button {
                Task { await confirm() }
            } label: {
                Text(sending ? "Sending…" : "Continue").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(sending || me.isEmpty)
        }
    }

    private func state(of stage: String) -> StageRow.State {
        let order = StageInfo.order
        guard let current = order.firstIndex(of: style.stage ?? "parsing"), let index = order.firstIndex(of: stage) else {
            return .waiting
        }
        if style.stage == "ready" { return .done }
        return index < current ? .done : index == current ? .working : .waiting
    }

    private func confirm() async {
        sending = true
        defer { sending = false }
        do {
            onChange(try await SaySoAPI.updateStyle(style.id, me: me, chats: chats))
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func poll() async {
        while !Task.isCancelled {
            if let fresh = try? await SaySoAPI.style(style.id), fresh != style { onChange(fresh) }
            if style.stage == "ready" || style.status == "failed" { return }
            try? await Task.sleep(for: .seconds(3))
        }
    }
}

struct StageRow: View {
    enum State { case waiting, working, done }
    let title: String
    let state: State

    var body: some View {
        HStack {
            switch state {
            case .done: Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
            case .working: ProgressView().controlSize(.small)
            case .waiting: Image(systemName: "circle").foregroundStyle(.tertiary)
            }
            Text(title).foregroundStyle(state == .waiting ? .secondary : .primary)
        }
    }
}

/// The self-check: how much the new style sounds like the user compared with a generic AI, and whether it makes sense.
struct SelfCheckSection: View {
    let scores: StyleScores
    let lora: String?

    var body: some View {
        Section {
            if let you = scores.soundsLikeYou {
                LabeledContent("Sounds like you") {
                    Text("\(Int(you * 100))%").bold() + Text(scores.generic.map { "  (generic AI \(Int($0 * 100))%)" } ?? "")
                        .foregroundStyle(.secondary)
                }
            }
            if let sense = scores.makesSense {
                LabeledContent("Makes sense", value: String(format: "%.1f / 5", sense))
            }
            ForEach(scores.samples ?? [], id: \.self) { sample in
                VStack(alignment: .leading, spacing: 4) {
                    Text("SaySo: \(sample.suggested)")
                    Text("You: \(sample.real.replacingOccurrences(of: "\n", with: " / "))").foregroundStyle(.secondary)
                }
                .font(.footnote)
            }
            if let note = scores.note { Text(note).font(.footnote).foregroundStyle(.secondary) }
        } header: {
            Text("Self-check")
        } footer: {
            Text(loraNote)
        }
    }

    private var loraNote: String {
        let checked = scores.checked.map { "Checked on \($0) of your real replies it hadn't seen. " } ?? ""
        switch lora {
        case "ready": return checked + "This style has its own model."
        case "training": return checked + "Its own model is training; until then Muse Spark writes in this style."
        case "waiting for GPU": return checked + "Its own model will train when the GPU is on; until then Muse Spark writes in this style."
        default: return checked + "Add more chats for this style to get its own model."
        }
    }
}
