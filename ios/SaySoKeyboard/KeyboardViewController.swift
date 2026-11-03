import SwiftUI
import UIKit

/// SaySo keyboard: its own letter keys with ✨ (the text in your style), or the panel (rewrite a draft typed with
/// another keyboard, write from an instruction, replies from the last screenshot or copied messages).
final class KeyboardViewController: UIInputViewController {
    private lazy var model = PanelModel(controller: self)
    private var watch: Timer?  // picks up the Back Tap shortcut's replies while the keyboard is up
    private var host: UIHostingController<KeyboardRoot>?

    override func viewDidLoad() {
        super.viewDidLoad()
        AppLanguage.install()
        let host = UIHostingController(rootView: KeyboardRoot(model: model, language: AppLanguage.current.code))
        self.host = host
        host.view.backgroundColor = .clear
        host.sizingOptions = []
        addChild(host)
        view.addSubview(host.view)
        host.view.translatesAutoresizingMaskIntoConstraints = false
        let height = host.view.heightAnchor.constraint(equalToConstant: 270)
        height.priority = .defaultHigh  // lets the system resize during rotation without layout warnings
        NSLayoutConstraint.activate([
            host.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            host.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            host.view.topAnchor.constraint(equalTo: view.topAnchor),
            host.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            height,
        ])
        host.didMove(toParent: self)
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        // The language picked in the app's Settings (read again on every open, so a change there shows up here).
        let language = AppLanguage.current.code
        if host?.rootView.language != language { host?.rootView = KeyboardRoot(model: model, language: language) }
        model.appear(fullAccess: hasFullAccess, needsGlobe: needsInputModeSwitchKey)
        watch?.invalidate()
        watch = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated { self?.model.checkShortcutReplies() }
        }
    }

    override func textDidChange(_ textInput: UITextInput?) {
        model.fieldChanged()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        watch?.invalidate()
        model.flush()
    }
}

/// The keyboard in the app's language: the SwiftUI locale for `Text("…")`, and a rebuild when the language changes so
/// strings kept in variables are read again.
struct KeyboardRoot: View {
    @ObservedObject var model: PanelModel
    let language: String

    var body: some View {
        PanelView(model: model)
            .environment(\.locale, AppLanguage.current.locale)
            .id(language)
    }
}
