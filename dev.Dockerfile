FROM python:3.12.2-slim-bookworm
ENV PYTHONUNBUFFERED=1 UV_VERSION=0.7.12

RUN pip3 install uv==$UV_VERSION
RUN uv venv --python 3.12 /usr/local/python
ENV VIRTUAL_ENV=/usr/local/python
WORKDIR /extension

ADD . /extension

RUN uv sync --locked --all-groups --active
ENV PATH="/usr/local/python/bin:$PATH"
CMD ["swoext", "run", "--no-color"]
