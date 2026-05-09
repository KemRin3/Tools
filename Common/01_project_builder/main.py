"""Entry point for the project builder GUI."""

from gui import ProjectBuilderApp


def main() -> None:
    """Start the tkinter application."""

    app = ProjectBuilderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
