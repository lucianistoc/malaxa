<?php

namespace modules\malaxa\twig;

use craft\elements\Asset;
use craft\helpers\UrlHelper;
use Twig\Extension\AbstractExtension;
use Twig\TwigFilter;

/**
 * Twig filters shared by the templates. They mirror helpers in the static generator (build.py),
 * so both versions render content the same way.
 */
class Extension extends AbstractExtension
{
    public function getFilters(): array
    {
        return [
            new TwigFilter('rich', [$this, 'rich'], ['is_safe' => ['html']]),
            new TwigFilter('drafts', [$this, 'drafts'], ['is_safe' => ['html']]),
            new TwigFilter('lines', [$this, 'lines'], ['is_safe' => ['html']]),
            new TwigFilter('byName', [$this, 'byName']),
            new TwigFilter('fileLabel', [$this, 'fileLabel']),
        ];
    }

    /**
     * Escape text; [[…]] marks a draft the hospital still has to confirm and is highlighted.
     * HIDE_PLACEHOLDERS=1 (public launch) renders drafts as plain text.
     */
    public function rich(?string $text): string
    {
        $cls = getenv('HIDE_PLACEHOLDERS') ? '' : ' class="placeholder"';
        return preg_replace('/\[\[(.*?)\]\]/su', '<span' . $cls . '>$1</span>', htmlspecialchars((string)$text, ENT_QUOTES));
    }

    /**
     * Rich-text (HTML) fields: the same [[…]] draft marking, and {siteUrl} in links resolved to the site URL
     * (the rich-text editor may store it URL-encoded).
     */
    public function drafts($html): string
    {
        $cls = getenv('HIDE_PLACEHOLDERS') ? '' : ' class="placeholder"';
        $html = str_replace(['{siteUrl}', '%7BsiteUrl%7D'], UrlHelper::siteUrl(), (string)$html);
        return preg_replace('/\[\[(.*?)\]\]/su', '<span' . $cls . '>$1</span>', $html);
    }

    /** Multi-line text: one paragraph per line; consecutive "– …" lines become a dashed list. */
    public function lines(?string $text): string
    {
        $out = '';
        $items = [];
        $flush = function() use (&$out, &$items) {
            if ($items) {
                $out .= '<ul class="list-check">' . implode('', array_map(fn($i) => '<li>' . $this->rich($i) . '</li>', $items)) . '</ul>';
                $items = [];
            }
        };
        foreach (preg_split('/\R/u', (string)$text) as $ln) {
            $ln = trim($ln);
            if ($ln === '') {
                continue;
            }
            if (preg_match('/^[–-]\s+(.*)$/u', $ln, $m)) {
                $items[] = $m[1];
            } else {
                $flush();
                $out .= '<p>' . $this->rich($ln) . '</p>';
            }
        }
        $flush();
        return $out;
    }

    /** Sort people alphabetically by surname, then first name, ignoring titles (Dr., Biol., Psiholog…) and diacritics. */
    public function byName(iterable $entries): array
    {
        $list = is_array($entries) ? $entries : iterator_to_array($entries, false);
        $key = function($e): string {
            $name = preg_replace('/^(Conf\. univ\. dr\.|Dr\.|Biol\.|Psiholog|Ec\.|Dna|Dl|As\. med\.( princ\.)?)\s*/u', '', (string)$e->title);
            $plain = \Normalizer::normalize(mb_strtolower($name), \Normalizer::FORM_D);
            return preg_replace('/\p{Mn}/u', '', $plain) . "\0" . $name;
        };
        usort($list, fn($a, $b) => strcmp($key($a), $key($b)));
        return $list;
    }

    /** "Regulament" + PDF asset → "Regulament (PDF, 240 KB)", like the static site's document links. */
    public function fileLabel(Asset $asset): string
    {
        $title = (string)$asset->title;
        $ext = strtoupper((string)$asset->getExtension());
        if (!in_array($ext, ['PDF', 'DOC', 'DOCX', 'XLS', 'XLSX'], true) || !$asset->size) {
            return $title;
        }
        $kb = $asset->size / 1024;
        $size = $kb >= 1024 ? str_replace('.', ',', sprintf('%.1f MB', $kb / 1024)) : max(1, (int)round($kb)) . ' KB';
        $title = preg_replace('/\s*\((PDF|DOCX?|XLSX?)\)\s*$/i', '', $title);
        return "$title ($ext, $size)";
    }
}
