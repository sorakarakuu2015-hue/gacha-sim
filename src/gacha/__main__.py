import uvicorn

from gacha.settings import settings


def main() -> None:
    uvicorn.run(
        "gacha.web.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
