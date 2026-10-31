import SwiftUI
import UIKit

/// SaySo keyboard: its own letter keys with ✨ (the text in your style), or the panel (rewrite a draft typed with
/// another keyboard, write from an instruction, replies from the last screenshot or copied messages).
final class KeyboardViewController: UIInputViewController {
    private lazy var model = PanelModel(controller: self)

    override func viewDidLoad() {
        super.viewDidLoad()
        let host = UIHostingController(rootView: PanelView(model: model))
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
        model.appear(fullAccess: hasFullAccess, needsGlobe: needsInputModeSwitchKey)
    }

    override func textDidChange(_ textInput: UITextInput?) {
        model.readDraft()
        model.autoShift()
    }
}
