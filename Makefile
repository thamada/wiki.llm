.PHONY: pdf clean c miru

WIKI_DIR ?= ./wiki
PATH_BUILD ?= ./build/

# wiki/ 内の全 .md を PATH_BUILD に PDF 出力する.
# latex から PDF への build には tectonic を使う
pdf:
	mkdir -p $(PATH_BUILD)
	@failed=0; \
	for md in $(WIKI_DIR)/*.md; do \
		[ -f "$$md" ] || continue; \
		echo "=== $$md ==="; \
		PATH_MARKDOWN="$$md" PATH_BUILD="$(PATH_BUILD)" ./gen_pdf.py || failed=$$((failed + 1)); \
	done; \
	if [ $$failed -gt 0 ]; then \
		echo "$$failed 件の PDF 生成に失敗しました" >&2; \
		exit 1; \
	fi


clean:
	rm -rf $(PATH_BUILD)

c: clean


miru:
	@for pdf in $(PATH_BUILD)*.pdf; do \
		[ -f "$$pdf" ] && open "$$pdf"; \
	done
