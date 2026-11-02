import SwiftUI

// Building blocks of the Styles tab and the style card: the hero card, kind-of-text cards, audience cards,
// habit bars, chat bubbles, chips. Everything here only displays a Style; loading and saving live in the views.

/// Colors and wording used only by the Styles screens.
enum StylePalette {
    /// The navy of the logo in both light and dark mode (Theme.navy turns light in dark mode, for text).
    static let deepNavy = Color(red: 0.043, green: 0.165, blue: 0.357)
    static let heroGradient = LinearGradient(colors: [deepNavy, Color(red: 0.12, green: 0.37, blue: 0.84), Color.accentColor],
                                             startPoint: .topLeading, endPoint: .bottomTrailing)
    static let messages = Theme.accentGradient
    static let emails = LinearGradient(colors: [Color(red: 0.12, green: 0.37, blue: 0.84), Theme.glow],
                                       startPoint: .bottomLeading, endPoint: .topTrailing)
    static let essays = LinearGradient(colors: [deepNavy, Color.accentColor],
                                       startPoint: .topLeading, endPoint: .bottomTrailing)

    static func percent(_ value: Double) -> String { "\(Int((value * 100).rounded()))%" }

    static func clamp(_ value: Double) -> Double { max(0, min(value, 1)) }

    static func emoji(_ audience: Audience) -> String {
        switch audience {
        case .partner: "💞"
        case .friends: "🍻"
        case .family: "🏠"
        case .elder_informal: "🎩"
        }
    }

    /// "~38 chars · mostly lowercase · no end dot": the few habits that make this audience's messages recognisable.
    static func signature(_ profile: AudienceProfile) -> String {
        var parts: [String] = []
        if let chars = profile.medianChars { parts.append("~\(Int(chars.rounded())) chars") }
        if let lower = profile.lowercaseStart {
            if lower >= 0.6 { parts.append("mostly lowercase") } else if lower <= 0.25 { parts.append("Capitalized") } else { parts.append("mixed case") }
        }
        if let punct = profile.endsWithPunctuation {
            if punct <= 0.3 { parts.append("no end dot") } else if punct >= 0.7 { parts.append("ends with a dot") }
        }
        if let laugh = profile.laughter, laugh >= 0.15 { parts.append("laughs a lot") }
        if let emoji = profile.emoji, emoji >= 0.15 { parts.append("emoji") }
        return parts.prefix(3).joined(separator: " · ")
    }

    /// The top shares of a habit map ("agree 40%, joke 22%"), most common first.
    static func top(_ shares: [String: Double], count: Int = 3) -> [String] {
        let sorted = shares.sorted { $0.value > $1.value }
        return sorted.prefix(count).map { "\($0.key.replacingOccurrences(of: "_", with: " ")) \(percent($0.value))" }
    }

    static func oneLine(_ text: String) -> String { text.replacingOccurrences(of: "\n", with: " / ") }
}

// MARK: - Hero

/// The active style at a glance: a big "sounds like you" score against a generic AI, on the brand gradient.
struct StyleHeroCard: View {
    let style: Style
    let isActive: Bool
    var onOpen: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            topRow
            if let you = style.scores?.soundsLikeYou {
                scoreBlock(you)
            } else if style.isBuilding {
                buildingBlock
            } else {
                Text("The self-check runs when this style is built.")
                    .font(.subheadline).foregroundStyle(.white.opacity(0.85))
            }
            if let onOpen {
                Button(action: onOpen) {
                    HStack(spacing: 6) {
                        Text("Open this style").font(Theme.label(15))
                        Image(systemName: "arrow.right").font(.subheadline.weight(.bold))
                    }
                    .foregroundStyle(StylePalette.deepNavy)
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .background(Color.white, in: .capsule)
                }
                .buttonStyle(.plain)
                .padding(.top, 2)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background { decoration }
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .shadow(color: Color.accentColor.opacity(0.35), radius: 18, y: 10)
    }

    private var topRow: some View {
        HStack(spacing: 8) {
            Text(badge)
                .font(Theme.label(11))
                .tracking(1)
                .foregroundStyle(StylePalette.deepNavy)
                .padding(.horizontal, 9).padding(.vertical, 4)
                .background(Color.white, in: .capsule)
            Text(style.name)
                .font(Theme.label(15))
                .foregroundStyle(.white)
                .lineLimit(1)
            Spacer(minLength: 0)
        }
    }

    private var badge: String {
        if isActive { return "IN USE" }
        return style.isBuilding ? "BUILDING" : "READY"
    }

    private func scoreBlock(_ you: Double) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(StylePalette.percent(you))
                    .font(Theme.display(64))
                    .foregroundStyle(.white)
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                Text("sounds\nlike you")
                    .font(Theme.label(15))
                    .foregroundStyle(.white.opacity(0.85))
            }
            VStack(spacing: 10) {
                StyleComparisonBar(title: "SaySo in your style", value: you, strong: true)
                if let generic = style.scores?.generic {
                    StyleComparisonBar(title: "Generic AI", value: generic, strong: false)
                }
            }
            if let footnote {
                Text(footnote).font(.caption).foregroundStyle(.white.opacity(0.75))
            }
        }
    }

    private var footnote: String? {
        var parts: [String] = []
        if let checked = style.scores?.checked { parts.append("Checked on \(checked) of your messages it never saw") }
        if let sense = style.scores?.makesSense { parts.append(String(format: "makes sense %.1f / 5", sense)) }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    private var buildingBlock: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(StageInfo.title(style.stage)).font(Theme.display(22)).foregroundStyle(.white)
            ProgressView(value: StylePalette.clamp(style.progress ?? 0))
                .tint(.white)
            Text("SaySo is reading your chats and checking itself. This takes a few minutes.")
                .font(.caption).foregroundStyle(.white.opacity(0.8))
        }
    }

    private var decoration: some View {
        ZStack(alignment: .topTrailing) {
            StylePalette.heroGradient
            Circle()
                .fill(Theme.glow.opacity(0.45))
                .frame(width: 220, height: 220)
                .blur(radius: 50)
                .offset(x: 60, y: -80)
        }
    }
}

/// One horizontal bar of the hero: how much a writer sounds like the user.
struct StyleComparisonBar: View {
    let title: String
    let value: Double
    let strong: Bool
    @State private var shown = false

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack {
                Text(title).font(.caption.weight(.semibold))
                Spacer()
                Text(StylePalette.percent(value)).font(Theme.label(13)).monospacedDigit()
            }
            .foregroundStyle(Color.white.opacity(strong ? 1 : 0.7))
            Capsule()
                .fill(Color.white.opacity(0.18))
                .frame(height: 10)
                .overlay(alignment: .leading) {
                    GeometryReader { geo in
                        Capsule()
                            .fill(Color.white.opacity(strong ? 1 : 0.45))
                            .frame(width: geo.size.width * (shown ? StylePalette.clamp(value) : 0))
                    }
                }
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.9)) { shown = true }
        }
    }
}

// MARK: - Small pieces

/// A rounded tile with a white SF Symbol on a blue gradient.
struct StyleIconTile: View {
    let icon: String
    let gradient: LinearGradient
    var size: CGFloat = 44

    var body: some View {
        Image(systemName: icon)
            .font(.system(size: size * 0.42, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(gradient, in: .rect(cornerRadius: Theme.card, style: .continuous))
            .shadow(color: Color.accentColor.opacity(0.3), radius: 6, y: 3)
    }
}

/// A small status capsule: filled (call to action) or soft (state).
struct StyleStatusChip: View {
    let text: String
    var icon: String? = nil
    var filled = false

    var body: some View {
        HStack(spacing: 4) {
            if let icon { Image(systemName: icon).font(.caption2.weight(.bold)) }
            Text(text).font(.caption.weight(.semibold))
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .foregroundStyle(filled ? Color.white : Color.accentColor)
        .background {
            if filled {
                Capsule().fill(Theme.accentGradient)
            } else {
                Capsule().fill(Color.accentColor.opacity(0.12))
            }
        }
    }
}

/// A habit as a thin labelled bar ("lowercase 82%").
struct StyleHabitBar: View {
    let label: String
    let value: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(label)
                Spacer(minLength: 4)
                Text(StylePalette.percent(value)).monospacedDigit()
            }
            .font(.caption2.weight(.medium))
            .foregroundStyle(.secondary)
            Capsule()
                .fill(Color.accentColor.opacity(0.12))
                .frame(height: 6)
                .overlay(alignment: .leading) {
                    GeometryReader { geo in
                        Capsule()
                            .fill(Theme.accentGradient)
                            .frame(width: max(6, geo.size.width * StylePalette.clamp(value)))
                    }
                }
        }
    }
}

/// One of the user's own messages, drawn as a sent chat bubble.
struct StyleBubble: View {
    let text: String
    var lineLimit: Int? = nil
    var mine = true

    var body: some View {
        Text(StylePalette.oneLine(text))
            .font(.footnote)
            .foregroundStyle(mine ? Color.white : Color.primary)
            .lineLimit(lineLimit)
            .multilineTextAlignment(.leading)
            .padding(.horizontal, 11).padding(.vertical, 7)
            .background(bubbleFill, in: bubbleShape)
            .frame(maxWidth: .infinity, alignment: mine ? .trailing : .leading)
    }

    private var bubbleFill: AnyShapeStyle {
        mine ? AnyShapeStyle(Theme.accentGradient) : AnyShapeStyle(Color.primary.opacity(0.07))
    }

    private var bubbleShape: UnevenRoundedRectangle {
        UnevenRoundedRectangle(topLeadingRadius: Theme.bubble,
                               bottomLeadingRadius: mine ? Theme.bubble : 4,
                               bottomTrailingRadius: mine ? 4 : Theme.bubble,
                               topTrailingRadius: Theme.bubble,
                               style: .continuous)
    }
}

/// A soft chip with text (a learned rule, a linking word, an act).
struct StyleChip: View {
    let text: String
    var icon: String? = nil

    var body: some View {
        HStack(spacing: 5) {
            if let icon { Image(systemName: icon).font(.caption2.weight(.bold)).foregroundStyle(Color.accentColor) }
            Text(text).font(.footnote).foregroundStyle(.primary)
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .background(.regularMaterial, in: .rect(cornerRadius: Theme.chip, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: Theme.chip, style: .continuous).stroke(Color.accentColor.opacity(0.18)))
    }
}

/// A big number with a label under it.
struct StyleStat: View {
    let value: Int
    let label: String
    var icon: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let icon { Image(systemName: icon).font(.subheadline.weight(.semibold)).foregroundStyle(Color.accentColor) }
            Text("\(value)").font(Theme.display(24)).foregroundStyle(Theme.navy)
            Text(label).font(.caption).foregroundStyle(.secondary).lineLimit(2)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.accentColor.opacity(0.08), in: .rect(cornerRadius: Theme.card, style: .continuous))
    }
}

/// A section heading with an optional line under it.
struct StyleSectionHeader: View {
    let title: String
    var subtitle: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            SectionTitle(text: title)
            if let subtitle { Text(subtitle).font(.footnote).foregroundStyle(.secondary) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Lays chips out left to right, wrapping to the next line.
struct StyleFlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        arrange(width: proposal.width ?? .infinity, subviews: subviews).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let frames = arrange(width: bounds.width, subviews: subviews).frames
        for (index, subview) in subviews.enumerated() where index < frames.count {
            let frame = frames[index]
            subview.place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY),
                          proposal: ProposedViewSize(width: frame.width, height: frame.height))
        }
    }

    private func arrange(width: CGFloat, subviews: Subviews) -> (frames: [CGRect], size: CGSize) {
        var frames: [CGRect] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var widest: CGFloat = 0
        for subview in subviews {
            var size = subview.sizeThatFits(.unspecified)
            if size.width > width {
                size = subview.sizeThatFits(ProposedViewSize(width: width, height: nil))
            }
            if x > 0 && x + size.width > width {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            frames.append(CGRect(x: x, y: y, width: size.width, height: size.height))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
            widest = max(widest, x - spacing)
        }
        return (frames, CGSize(width: widest, height: y + rowHeight))
    }
}

// MARK: - Kind of text

/// A tall card for one kind of text (messages, emails, essays): how much SaySo has of it, or a "Teach me" call.
struct StyleKindCard: View {
    let icon: String
    let gradient: LinearGradient
    let title: String
    let count: Int
    let unit: String
    let detail: String
    let status: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 8) {
                StyleIconTile(icon: icon, gradient: gradient)
                Spacer(minLength: 6)
                Text(title).font(Theme.label(15)).foregroundStyle(.primary).lineLimit(2)
                if count > 0 {
                    HStack(alignment: .firstTextBaseline, spacing: 5) {
                        Text("\(count)").font(Theme.display(30)).foregroundStyle(Theme.navy)
                            .minimumScaleFactor(0.6).lineLimit(1)
                        Text(unit).font(.caption).foregroundStyle(.secondary)
                    }
                } else {
                    Text("Not yet").font(Theme.display(20)).foregroundStyle(.secondary)
                }
                Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                if count > 0 {
                    StyleStatusChip(text: status, icon: "checkmark")
                } else {
                    StyleStatusChip(text: "Teach me", icon: "plus", filled: true)
                }
            }
            .padding(16)
            .frame(width: 180, height: 260, alignment: .topLeading)
            .background(.regularMaterial, in: .rect(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(Color.primary.opacity(0.06)))
            .shadow(color: Theme.glow.opacity(0.18), radius: 12, y: 6)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Audience

/// A grid card: how the user writes to one kind of person, with one real example.
struct StyleAudienceCard: View {
    let audience: Audience
    let profile: AudienceProfile
    let example: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(alignment: .top) {
                Text(StylePalette.emoji(audience))
                    .font(.system(size: 22))
                    .frame(width: 42, height: 42)
                    .background(Color.accentColor.opacity(0.12), in: .rect(cornerRadius: Theme.card, style: .continuous))
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(.tertiary)
            }
            Text(audience.label).font(Theme.display(17)).foregroundStyle(.primary)
            let signature = StylePalette.signature(profile)
            if !signature.isEmpty {
                Text(signature).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            VStack(spacing: 6) {
                if let lower = profile.lowercaseStart { StyleHabitBar(label: "lowercase", value: lower) }
                if let punct = profile.endsWithPunctuation { StyleHabitBar(label: "end punctuation", value: punct) }
                StyleHabitBar(label: "emoji & laughs", value: StylePalette.clamp((profile.emoji ?? 0) + (profile.laughter ?? 0)))
            }
            if let example {
                StyleBubble(text: example, lineLimit: 2)
                    .padding(.top, 2)
            }
            Spacer(minLength: 0)
        }
        .frame(maxHeight: .infinity, alignment: .top)
        .glassCard(radius: 20, padding: 14)
    }
}

/// The full picture of one audience on the style card: habits, usual moves and tone, all examples.
struct StyleAudienceDetail: View {
    let audience: Audience
    let profile: AudienceProfile
    let examples: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            header
            habits
            if let acts = profile.acts, !acts.isEmpty {
                chipRow(title: "Usually", items: StylePalette.top(acts))
            }
            if let tones = profile.tones, !tones.isEmpty {
                chipRow(title: "Tone", items: StylePalette.top(tones))
            }
            if !examples.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("How you actually write").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    ForEach(examples, id: \.self) { example in
                        StyleBubble(text: example)
                    }
                }
            }
        }
        .glassCard(radius: 20, padding: 16)
    }

    private var header: some View {
        HStack(spacing: 12) {
            Text(StylePalette.emoji(audience))
                .font(.system(size: 24))
                .frame(width: 46, height: 46)
                .background(Color.accentColor.opacity(0.12), in: .rect(cornerRadius: Theme.card, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(audience.label).font(Theme.display(19))
                let signature = StylePalette.signature(profile)
                if !signature.isEmpty {
                    Text(signature).font(.caption).foregroundStyle(.secondary)
                }
            }
            Spacer(minLength: 0)
            if let turns = profile.turns {
                VStack(alignment: .trailing, spacing: 0) {
                    Text("\(turns)").font(Theme.label(15)).foregroundStyle(Theme.navy)
                    Text("messages").font(.caption2).foregroundStyle(.secondary)
                }
            }
        }
    }

    private var habits: some View {
        VStack(spacing: 7) {
            if let lower = profile.lowercaseStart { StyleHabitBar(label: "Starts lowercase", value: lower) }
            if let punct = profile.endsWithPunctuation { StyleHabitBar(label: "Ends with punctuation", value: punct) }
            if let emoji = profile.emoji { StyleHabitBar(label: "Emoji", value: emoji) }
            if let laugh = profile.laughter { StyleHabitBar(label: "Laughter", value: laugh) }
            if let swear = profile.swear, swear > 0.05 { StyleHabitBar(label: "Swearing", value: swear) }
        }
    }

    private func chipRow(title: String, items: [String]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            StyleFlowLayout(spacing: 6) {
                ForEach(items, id: \.self) { item in
                    StyleChip(text: item)
                }
            }
        }
    }
}

// MARK: - Teach and other styles

/// One way to teach SaySo more, as a wide card.
struct TeachCard: View {
    let icon: String
    let title: String
    let detail: String
    var gradient: LinearGradient = Theme.accentGradient
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                StyleIconTile(icon: icon, gradient: gradient)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(Theme.label(15)).foregroundStyle(.primary)
                    Text(detail).font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 4)
                Image(systemName: "plus.circle.fill").font(.title2).foregroundStyle(Color.accentColor)
            }
            .glassCard(padding: 12)
        }
        .buttonStyle(.plain)
    }
}

/// Another style in the list: its score, or its progress while it is being built.
struct StyleRow: View {
    let style: Style
    let isActive: Bool

    var body: some View {
        HStack(spacing: 12) {
            StyleIconTile(icon: isActive ? "checkmark" : "person.text.rectangle",
                          gradient: isActive ? Theme.accentGradient : StylePalette.essays, size: 38)
            VStack(alignment: .leading, spacing: 4) {
                Text(style.name).font(Theme.label(15)).foregroundStyle(.primary).lineLimit(1)
                if style.isBuilding, style.stage != "training" {
                    ProgressView(value: StylePalette.clamp(style.progress ?? 0)) {
                        Text(StageInfo.title(style.stage)).font(.caption).foregroundStyle(.secondary)
                    }
                } else if style.status == "failed" {
                    Text(style.error ?? "Couldn't build this style.").font(.caption).foregroundStyle(.red).lineLimit(2)
                } else {
                    Text(summary).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                }
            }
            Spacer(minLength: 4)
            if let score = style.scores?.soundsLikeYou {
                Text(StylePalette.percent(score))
                    .font(Theme.label(14))
                    .foregroundStyle(Theme.navy)
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(Color.accentColor.opacity(0.12), in: .capsule)
            }
            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
        }
        .glassCard(padding: 12)
    }

    private var summary: String {
        var parts: [String] = []
        if let turns = style.counts?["turns"], turns > 0 { parts.append("\(turns) messages") }
        if let sense = style.scores?.makesSense { parts.append(String(format: "makes sense %.1f/5", sense)) }
        if style.stage == "training" { parts.append("training its own model…") }
        else if style.adapterReady == true { parts.append("Muse Spark Open writes in this style") }
        if parts.isEmpty { parts.append(style.source ?? "ready") }
        return parts.joined(separator: " · ")
    }
}
