import SwiftUI

/// ✨ results in place of the keys: each variant a card; a series is a stack of messages like grouped notifications.
struct ResultsView: View {
    @ObservedObject var model: PanelModel

    private var accent: Color { KeyTheme.accent(model.settings.accent) }

    var body: some View {
        VStack(spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: model.series.isEmpty ? "sparkles" : "square.stack.fill")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(accent)
                Text(model.series.isEmpty ? "In your style" : "Series · \(model.seriesIndex + 1) of \(model.series.count) sent")
                    .font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                if !model.series.isEmpty {
                    SeriesProgress(count: model.series.count, sent: model.seriesIndex + 1, accent: accent)
                }
                Spacer()
                Button { model.closeResults() } label: {
                    Image(systemName: "xmark.circle.fill").font(.title3).symbolRenderingMode(.hierarchical)
                }
                .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 4)
            ScrollView {
                VStack(spacing: 8) {
                    if !model.series.isEmpty {
                        NextPartCard(model: model, accent: accent)
                    } else {
                        ForEach(model.options) { option in
                            if option.parts.count > 1 {
                                SeriesStack(parts: option.parts, label: option.label, accent: accent) { model.insert(option) }
                            } else {
                                OptionCard(option: option, accent: accent) { model.insert(option) }
                            }
                        }
                    }
                }
                .padding(.horizontal, 4)
                .padding(.top, 2)
                .padding(.bottom, 10)  // room for the bubbles' glow
            }
            .scrollIndicators(.hidden)
        }
        .padding(.horizontal, 6)
    }
}

/// How far a series has been sent: one dot per message.
struct SeriesProgress: View {
    let count: Int
    let sent: Int
    let accent: Color

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<max(count, 0), id: \.self) { index in
                Capsule()
                    .fill(index < sent ? accent : Color.secondary.opacity(0.3))
                    .frame(width: index < sent ? 12 : 6, height: 4)
            }
        }
    }
}

/// An outgoing chat bubble in the accent: rounded, with the tail corner at the bottom right, lit from above.
struct AccentBubble: View {
    let accent: Color
    var tail = true

    var body: some View {
        let shape = UnevenRoundedRectangle(topLeadingRadius: KeyTheme.bubble, bottomLeadingRadius: KeyTheme.bubble,
                                           bottomTrailingRadius: tail ? 4 : KeyTheme.bubble,
                                           topTrailingRadius: KeyTheme.bubble, style: .continuous)
        ZStack {
            shape.fill(accent)
            shape.fill(KeyTheme.gloss)
            shape.stroke(Color.white.opacity(0.18), lineWidth: 0.5)
        }
    }
}

/// One variant as a sent-message bubble on the right, like in iMessage; tap puts it in the field.
struct OptionCard: View {
    let option: PanelOption
    var accent: Color = KeyTheme.brandBlue
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .bottom, spacing: 6) {
                Spacer(minLength: 24)
                VStack(alignment: .trailing, spacing: 3) {
                    if let label = option.label {
                        Text(label.replacingOccurrences(of: "_", with: " ").uppercased())
                            .font(.system(size: 9, weight: .bold))
                            .tracking(0.6)
                            .foregroundStyle(accent)
                            .padding(.trailing, 6)
                    }
                    HStack(alignment: .top, spacing: 8) {
                        Text(option.text)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                        Image(systemName: "arrow.down.left")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(Color.white.opacity(0.75))
                            .padding(.top, 3)
                    }
                    .foregroundStyle(Color.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background { AccentBubble(accent: accent) }
                    .shadow(color: accent.opacity(0.35), radius: 6, x: 0, y: 3)
                }
            }
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
    }
}

/// The first message on top, the rest peeking out underneath ("+2"); tap the header to see them all.
struct SeriesStack: View {
    let parts: [String]
    let label: String?
    var accent: Color = KeyTheme.brandBlue
    let action: () -> Void

    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Button { withAnimation(.snappy) { expanded.toggle() } } label: {
                HStack(spacing: 4) {
                    Image(systemName: "square.stack")
                    Text(Lf("%lld messages", parts.count) + (label.map { " · " + $0.replacingOccurrences(of: "_", with: " ") } ?? ""))
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                }
                .font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
            Button(action: action) {
                if expanded {
                    VStack(alignment: .trailing, spacing: 3) {
                        ForEach(Array(parts.enumerated()), id: \.offset) { index, part in
                            bubble(part, depth: 0, tail: index == parts.count - 1)
                        }
                    }
                    .padding(.leading, 24)
                } else {
                    ZStack(alignment: .top) {
                        ForEach(Array(parts.prefix(3).enumerated().reversed()), id: \.offset) { index, part in
                            bubble(index == 0 ? part : " ", depth: index, tail: index == 0)
                                .scaleEffect(x: 1 - CGFloat(index) * 0.06, anchor: .top)
                                .offset(y: CGFloat(index) * 7)
                        }
                    }
                    .padding(.bottom, CGFloat(min(parts.count, 3) - 1) * 7)
                    .overlay(alignment: .bottomTrailing) {
                        Text("+\(parts.count - 1)")
                            .font(.caption2.weight(.heavy))
                            .foregroundStyle(accent)
                            .padding(.horizontal, 7).padding(.vertical, 2)
                            .background(Color.white, in: .capsule)
                            .shadow(color: KeyTheme.navy.opacity(0.18), radius: 3, x: 0, y: 1)
                            .offset(x: -6, y: -2)
                    }
                }
            }
            .buttonStyle(.plain)
        }
    }

    /// A message bubble; the ones further back are paler, so the stack has depth.
    private func bubble(_ text: String, depth: Int, tail: Bool) -> some View {
        Text(text)
            .foregroundStyle(Color.white)
            .frame(maxWidth: .infinity, alignment: .leading)
            .lineLimit(2)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background {
                AccentBubble(accent: accent, tail: tail)
                    .opacity(depth == 0 ? 1 : (depth == 1 ? 0.55 : 0.32))
            }
            .shadow(color: accent.opacity(depth == 0 ? 0.35 : 0.12), radius: depth == 0 ? 6 : 3, x: 0, y: 3)
    }
}

/// While a series is being sent: send the part in the field, then tap here for the next one.
struct NextPartCard: View {
    @ObservedObject var model: PanelModel
    var accent: Color = KeyTheme.brandBlue

    var body: some View {
        let next = model.seriesIndex + 1 < model.series.count ? model.series[model.seriesIndex + 1] : nil
        VStack(alignment: .leading, spacing: 6) {
            Label("Send this one, then tap the next", systemImage: "paperplane")
                .font(.caption).foregroundStyle(.secondary)
            if let next {
                Button(action: model.insertNextPart) {
                    HStack(alignment: .top, spacing: 8) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("NEXT")
                                .font(.system(size: 9, weight: .bold))
                                .tracking(0.6)
                                .foregroundStyle(Color.white.opacity(0.8))
                            Text(next).foregroundStyle(Color.white)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        Image(systemName: "arrow.down.left")
                            .font(.caption.weight(.bold))
                            .foregroundStyle(Color.white.opacity(0.85))
                            .padding(.top, 2)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background { AccentBubble(accent: accent) }
                    .shadow(color: accent.opacity(0.35), radius: 6, x: 0, y: 3)
                }
                .buttonStyle(.plain)
            }
            ForEach(Array(model.series.enumerated()).dropFirst(model.seriesIndex + 2), id: \.offset) { _, part in
                Text(part).font(.footnote).foregroundStyle(.secondary).lineLimit(1).padding(.horizontal, 10)
            }
        }
    }
}
