<?php

namespace modules\malaxa\console\controllers;

use Craft;
use craft\base\FieldInterface;
use craft\ckeditor\Field as CkeField;
use craft\console\Controller;
use craft\elements\Entry;
use craft\elements\GlobalSet;
use craft\fieldlayoutelements\CustomField;
use craft\fieldlayoutelements\entries\EntryTitleField;
use craft\fields\Assets;
use craft\fields\Color;
use craft\fields\Dropdown;
use craft\fields\Entries;
use craft\fields\Lightswitch;
use craft\fields\Matrix;
use craft\fields\PlainText;
use craft\fields\Table;
use craft\fs\Local;
use craft\models\EntryType;
use craft\models\FieldLayout;
use craft\models\FieldLayoutTab;
use craft\models\Section;
use craft\models\Section_SiteSettings;
use craft\models\Volume;
use yii\console\ExitCode;

/**
 * Builds the content model (fields, entry types, sections, volume, globals).
 *
 *     php craft malaxa/schema
 *
 * Safe to re-run: existing fields and sections are kept; entry type layouts are refreshed. The result is
 * written to config/project/*.yaml, which is what gets committed and deployed.
 */
class SchemaController extends Controller
{
    public const ICONS = ['stethoscope', 'run', 'microscope', 'heartbeat', 'virus', 'heart', 'scalpel', 'ambulance', 'skin', 'document', 'gland', 'shield', 'drop', 'flask', 'clipboard', 'helmet', 'brain', 'female', 'eye', 'ribbon', 'ear', 'mind', 'xray', 'atom', 'phone', 'mail', 'pin', 'clock', 'arrow', 'user', 'chat', 'cart', 'contract', 'handshake', 'chart', 'pen', 'people', 'money', 'pill', 'gavel', 'star', 'check', 'org', 'hands', 'hospital', 'award', 'cpu', 'facebook', 'instagram', 'youtube', 'linkedin', 'a11y', 'calendar', 'metro', 'bus', 'tram', 'download', 'tooth', 'external', 'building'];

    private ?Volume $volume = null;
    /** @var array<string, FieldInterface> */
    private array $fields = [];

    public function actionIndex(): int
    {
        $this->volume = $this->ensureVolume();

        $this->createFields();
        $blockTypes = $this->createBlockTypes();
        $this->field(Matrix::class, 'contentBlocks', 'Blocuri de conținut', [
            'instructions' => 'Construiește pagina din blocuri: text, liste, tabele, acordeoane, documente, carduri, galerie.',
            'entryTypes' => $blockTypes,
            'viewMode' => Matrix::VIEW_MODE_BLOCKS,
            'showCardsInGrid' => false,
        ]);
        /** @var Matrix $blocks */
        $blocks = $this->fields['contentBlocks'];
        if (array_map(fn($t) => $t->handle, $blocks->getEntryTypes()) !== array_map(fn($t) => $t->handle, $blockTypes)) {
            $blocks->setEntryTypes($blockTypes);
            Craft::$app->getFields()->saveField($blocks);
            $this->stdout("  field contentBlocks: block types updated\n");
        }

        // Sections that other fields relate to must exist first. The hospital (Spital) and the outpatient
        // clinic (Ambulatoriu) are separate sections that share one template, so both show the same
        // information in the same order.
        $unitTabs = fn(bool $hospital) => [
            'Conținut' => array_merge(['iconName'], $hospital ? ['unitCategory'] : [], ['summary', 'beds', 'body', 'contentBlocks', 'equipment', 'gallery', 'pending']),
            'Program și contact' => ['hours', 'schedule', 'phones'],
        ];
        $hospital = $this->section('hospital', 'Spital – secții și servicii', Section::TYPE_STRUCTURE, 'service/{slug}', '_units/entry', [
            $this->entryType('hospitalUnit', 'Structură spital', $unitTabs(true)),
        ]);
        $ambulatory = $this->section('ambulatory', 'Ambulatoriu – cabinete', Section::TYPE_STRUCTURE, 'ambulatoriu/{slug}', '_units/entry', [
            $this->entryType('cabinet', 'Cabinet ambulatoriu', $unitTabs(false)),
        ]);
        $priceGroups = $this->section('priceGroups', 'Tarife', Section::TYPE_STRUCTURE, null, null, [
            $this->entryType('priceGroup', 'Grupă de tarife', ['Conținut' => ['priceItems']]),
        ]);
        $this->field(Entries::class, 'priceGroup', 'Grupă de tarife', [
            'sources' => ['section:' . $priceGroups->uid], 'maxRelations' => 1,
            'instructions' => 'Tarifele afișate pe pagina structurii sau a cabinetului.',
        ]);
        $this->field(Entries::class, 'relatedUnit', 'Structură asociată', [
            'sources' => ['section:' . $hospital->uid, 'section:' . $ambulatory->uid], 'maxRelations' => 1,
            'instructions' => 'Secția din spital care corespunde cabinetului (sau invers); apare la „Vezi și”.',
        ]);
        $this->field(Entries::class, 'hospitalUnit', 'Secție / compartiment (spital)', [
            'sources' => ['section:' . $hospital->uid], 'maxRelations' => 1,
            'instructions' => 'Lăsați gol dacă medicul lucrează doar în ambulatoriu.',
        ]);
        $this->field(Entries::class, 'cabinet', 'Cabinet (ambulatoriu)', [
            'sources' => ['section:' . $ambulatory->uid], 'maxRelations' => 1,
            'instructions' => 'Lăsați gol dacă medicul nu consultă în ambulatoriu.',
        ]);
        // Now that the relation fields exist, add the "Legături" and "Tarife" tabs.
        foreach ([['hospitalUnit', 'Structură spital', true], ['cabinet', 'Cabinet ambulatoriu', false]] as [$h, $n, $isHosp]) {
            $this->entryType($h, $n, $unitTabs($isHosp) + ['Legături' => ['relatedUnit', 'relatedLinks'], 'Tarife' => ['priceGroup']], true, null, true);
        }
        $this->pruneOldModel();

        $this->section('doctors', 'Medici', Section::TYPE_STRUCTURE, 'team/{slug}', '_doctors/entry', [
            $this->entryType('doctor', 'Medic', ['Conținut' => ['grade', 'role', 'hospitalUnit', 'cabinet', 'photo', 'bio']], true, null, true),
        ]);
        $this->section('news', 'Noutăți', Section::TYPE_CHANNEL, 'noutati/{slug}', '_news/entry', [
            $this->entryType('newsItem', 'Articol', ['Conținut' => ['category', 'showDate', 'excerpt', 'image', 'body', 'attachment', 'linkUrl']]),
        ]);
        $pages = null;
        $pageLayout = ['Conținut' => ['heading', 'body', 'contentBlocks', 'showToc'], 'Navigare' => ['hideFromNav', 'navGroup', 'linkUrl']];
        $pageTypes = array_map(fn($t) => $this->entryType($t[0], $t[1], $pageLayout, true, null, true), [
            ['page', 'Pagină'],
            ['hospitalIndex', 'Listă spital'],
            ['ambulatoryIndex', 'Listă ambulatoriu'],
            ['doctorsIndex', 'Listă medici'],
            ['newsIndex', 'Listă noutăți'],
            ['pricesPage', 'Pagină plata serviciilor / tarife'],
            ['presentationPage', 'Pagină tipuri de prezentare'],
            ['publicInterest', 'Pagină interes public'],
            ['contactPage', 'Pagină contact'],
        ]);
        $pages = $this->section('pages', 'Pagini', Section::TYPE_STRUCTURE, '{slug}', '_pages/entry', $pageTypes);
        $this->field(Entries::class, 'linkedPage', 'Pagină asociată', [
            'sources' => ['section:' . $pages->uid], 'maxRelations' => 1,
            'instructions' => 'Opțional: în loc de documente, cardul trimite către această pagină.',
        ]);
        $this->section('documentGroups', 'Documente de interes public', Section::TYPE_STRUCTURE, null, null, [
            $this->entryType('documentGroup', 'Grupă de documente', ['Conținut' => ['iconName', 'note', 'documents', 'docLinks', 'linkedPage', 'linkUrl']]),
        ]);
        $this->section('homepage', 'Pagina principală', Section::TYPE_SINGLE, '__home__', '_pages/home', [
            $this->entryType('homepage', 'Pagina principală', ['Conținut' => ['heading', 'body', 'image', 'cardItems']]),
        ]);

        $this->globalSet('siteSettings', 'Setări site', [
            'Identitate' => ['legalName', 'tagline', 'logoIcon', 'logoText', 'logoSubtext', 'badgeImage', 'founded'],
            'Hero' => ['heroTitle', 'heroSubtitle', 'heroImage', 'stats'],
            'Contact' => ['phone', 'phoneAppointments', 'fax', 'phoneHr', 'email', 'emailOffice', 'emailIntegrity', 'spokesperson', 'address', 'addressShort', 'mapQuery', 'bookingUrl', 'feedbackUrl', 'audiences', 'transport'],
            'Vizită' => ['visiting', 'visitingPdf'],
            'Actualizare' => ['contentUpdated'],
            'Linkuri' => ['socialLinks', 'externalLinks'],
            'Culori' => ['colorPrimary', 'colorPrimaryDark', 'colorAccent', 'colorAccentDark', 'colorHighlight', 'colorSoft'],
        ]);

        $this->stdout("Content model ready.\n");
        return ExitCode::OK;
    }

    // ------------------------------------------------------------------ fields

    private function createFields(): void
    {
        $text = fn(string $h, string $n, array $c = []) => $this->field(PlainText::class, $h, $n, $c);
        $multi = fn(string $h, string $n, array $c = []) => $this->field(PlainText::class, $h, $n, ['multiline' => true, 'initialRows' => 3] + $c);
        $list = fn(string $h, string $n, string $col = 'Text', array $c = []) => $this->field(Table::class, $h, $n, [
            'columns' => ['col1' => ['heading' => $col, 'handle' => 'text', 'type' => 'singleline', 'width' => '']],
            'addRowLabel' => 'Adaugă rând',
        ] + $c);
        $table = fn(string $h, string $n, array $cols, array $c = []) => $this->field(Table::class, $h, $n, [
            'columns' => array_combine(
                array_map(fn($i) => 'col' . ($i + 1), array_keys($cols)),
                array_map(fn($col) => ['heading' => $col[1], 'handle' => $col[0], 'type' => $col[2] ?? 'singleline', 'width' => ''], $cols),
            ),
            'addRowLabel' => 'Adaugă rând',
        ] + $c);
        $vol = 'volume:' . $this->volume->uid;
        $asset = fn(string $h, string $n, bool $single, ?array $kinds, array $c = []) => $this->field(Assets::class, $h, $n, [
            'sources' => [$vol],
            'maxRelations' => $single ? 1 : null,
            'restrictFiles' => $kinds !== null,
            'allowedKinds' => $kinds,
            'defaultUploadLocationSource' => $vol,
            'defaultUploadLocationSubpath' => $kinds === ['image'] ? 'images' : 'docs',
            'viewMode' => $kinds === ['image'] ? 'large' : 'list',
        ] + $c);
        $switch = fn(string $h, string $n, array $c = []) => $this->field(Lightswitch::class, $h, $n, $c);

        // Generic
        $text('heading', 'Titlu secțiune');
        $text('summary', 'Rezumat', ['instructions' => 'O frază, folosită pe carduri.']);
        $this->field(CkeField::class, 'body', 'Text', [
            'toolbar' => ['heading', '|', 'bold', 'italic', 'link', '|', 'bulletedList', 'numberedList', '|', 'blockQuote', 'insertTable', '|', 'sourceEditing'],
            'headingLevels' => [2, 3, 4],
        ]);
        $this->field(Dropdown::class, 'iconName', 'Iconiță', [
            'options' => array_map(fn($i) => ['label' => $i, 'value' => $i, 'default' => $i === 'hospital'], self::ICONS),
        ]);
        $asset('image', 'Imagine', true, ['image']);
        $asset('gallery', 'Galerie foto', false, ['image']);
        $asset('documents', 'Documente', false, null);
        $asset('attachment', 'Fișier atașat', true, null);
        $text('linkUrl', 'Link extern', ['instructions' => 'URL complet (https://…).']);
        $text('note', 'Notă');
        $list('listItems', 'Elemente listă', 'Element');
        $text('tableHeadings', 'Capete de tabel', ['instructions' => 'Separate prin „|”, ex.: Secție | Paturi']);
        $table('tableRows', 'Rânduri tabel', [['c1', 'Coloana 1'], ['c2', 'Coloana 2'], ['c3', 'Coloana 3']]);
        $table('accordionItems', 'Elemente acordeon', [['question', 'Titlu / întrebare'], ['answer', 'Conținut / răspuns', 'multiline']]);
        $table('cardItems', 'Carduri', [['title', 'Titlu'], ['text', 'Text', 'multiline'], ['icon', 'Iconiță'], ['url', 'Link']]);
        $table('docLinks', 'Linkuri', [['title', 'Titlu'], ['url', 'URL']]);
        $this->fields['relatedLinks'] = $this->fields['docLinks'];

        // Hospital structures and outpatient cabinets
        $this->field(Dropdown::class, 'unitCategory', 'Categorie', [
            'options' => [
                ['label' => 'Secții și compartimente clinice', 'value' => 'clinic', 'default' => true],
                ['label' => 'Laboratoare și servicii paraclinice', 'value' => 'paraclinic'],
                ['label' => 'Alte structuri', 'value' => 'other'],
            ],
        ]);
        $text('beds', 'Paturi');
        $list('hours', 'Program');
        $table('schedule', 'Program medici', [['doctor', 'Medic'], ['program', 'Program']]);
        $list('phones', 'Programări și contact');
        $list('equipment', 'Dotări');
        $switch('pending', 'Informații în curs de actualizare', ['instructions' => 'Afișează mesajul că programul și medicii sunt în curs de actualizare.']);
        $text('anchor', 'Ancoră', ['instructions' => 'Opțional: ID pentru link direct către acest bloc (ex.: ca → pagina#ca).']);
        $table('presentationRows', 'Rânduri', [['label', 'Titlu (ex.: Condiții)'], ['text', 'Text (un rând = un paragraf; rândurile care încep cu „– ” devin listă)', 'multiline']]);

        // Doctor
        $text('grade', 'Grad profesional');
        $text('role', 'Funcție', ['instructions' => 'Ex.: Șef secție, Coordonator.']);
        $asset('photo', 'Fotografie', true, ['image']);
        $multi('bio', 'Despre medic');

        // News
        $text('category', 'Categorie');
        $switch('showDate', 'Afișează data publicării');
        $multi('excerpt', 'Rezumat');

        // Prices
        $table('priceItems', 'Servicii și tarife', [['service', 'Serviciu'], ['price', 'Tarif']]);

        // Pages
        $switch('hideFromNav', 'Ascunde din meniu');
        $switch('showToc', 'Cuprins', ['instructions' => 'Afișează sus butoane către blocurile care au ancoră.']);
        $text('navGroup', 'Grup în meniu', ['instructions' => 'Opțional: titlul grupului din submeniu (ex.: Pentru pacienți).']);

        // Globals
        foreach ([
            'legalName' => 'Denumire oficială', 'tagline' => 'Slogan', 'logoText' => 'Logo – text', 'logoSubtext' => 'Logo – subtext',
            'founded' => 'Anul înființării', 'heroTitle' => 'Hero – titlu', 'phone' => 'Telefon centrală', 'phoneAppointments' => 'Telefon programări',
            'fax' => 'Fax', 'phoneHr' => 'Telefon resurse umane', 'email' => 'Email', 'emailOffice' => 'Email office', 'emailIntegrity' => 'Email integritate',
            'spokesperson' => 'Purtător de cuvânt', 'address' => 'Adresă', 'addressShort' => 'Adresă scurtă', 'mapQuery' => 'Hartă – căutare Google Maps',
            'bookingUrl' => 'Programări online – URL', 'feedbackUrl' => 'Chestionar feedback – URL',
        ] as $h => $n) {
            $text($h, $n);
        }
        $multi('heroSubtitle', 'Hero – subtitlu');
        $text('contentUpdated', 'Ultima actualizare', ['instructions' => 'Data afișată pe paginile cu program, tarife și contact (ZZ.LL.AAAA).']);
        $asset('heroImage', 'Hero – imagine', true, ['image']);
        $asset('logoIcon', 'Logo – emblemă', true, ['image']);
        $asset('badgeImage', 'Siglă acreditare', true, ['image']);
        $asset('visitingPdf', 'Program vizită (PDF)', true, null);
        $table('stats', 'Cifre', [['value', 'Valoare', 'number'], ['label', 'Etichetă']]);
        $list('audiences', 'Program audiențe');
        $table('transport', 'Transport', [['label', 'Mijloc'], ['text', 'Linii / stații'], ['icon', 'Iconiță']]);
        $table('visiting', 'Program de vizită', [['section', 'Secție'], ['line1', 'Program'], ['line2', 'Program (2)']]);
        $table('socialLinks', 'Rețele sociale', [['network', 'Rețea (facebook, instagram, youtube, linkedin)'], ['url', 'URL']]);
        $this->fields['externalLinks'] = $this->field(Table::class, 'externalLinks', 'Linkuri utile', [
            'columns' => ['col1' => ['heading' => 'Titlu', 'handle' => 'title', 'type' => 'singleline', 'width' => ''], 'col2' => ['heading' => 'URL', 'handle' => 'url', 'type' => 'singleline', 'width' => '']],
        ]);
        foreach (['colorPrimary' => 'Culoare principală', 'colorPrimaryDark' => 'Culoare principală (închisă)', 'colorAccent' => 'Culoare accent',
                     'colorAccentDark' => 'Culoare accent (închisă)', 'colorHighlight' => 'Culoare evidențiere', 'colorSoft' => 'Culoare fundal deschis'] as $h => $n) {
            $this->field(Color::class, $h, $n, ['allowCustomColors' => true]);
        }
    }

    /** @return EntryType[] */
    private function createBlockTypes(): array
    {
        $types = [
            ['blockText', 'Text', ['heading', 'body']],
            ['blockMedia', 'Text cu imagine', ['heading', 'body', 'image']],
            ['blockList', 'Listă', ['heading', 'listItems']],
            ['blockTable', 'Tabel', ['heading', 'tableHeadings', 'tableRows']],
            ['blockAccordion', 'Acordeon', ['heading', 'accordionItems']],
            ['blockDocuments', 'Documente', ['heading', 'documents', 'docLinks']],
            ['blockCards', 'Carduri', ['heading', 'cardItems']],
            ['blockGallery', 'Galerie', ['heading', 'gallery']],
            ['blockNotice', 'Atenționare', ['note']],
            ['blockPresentation', 'Tip de prezentare', ['heading', 'iconName', 'presentationRows']],
        ];
        return array_map(fn($t) => $this->entryType($t[0], $t[1], ['Conținut' => array_merge($t[2], ['anchor'])], false, null, true), $types);
    }

    /** Removes the old combined "Specialități medicale" model (replaced by the hospital and ambulatory sections). */
    private function pruneOldModel(): void
    {
        $entries = Craft::$app->getEntries();
        if ($old = $entries->getSectionByHandle('specialties')) {
            $entries->deleteSection($old);
            $this->stdout("  removed section specialties\n");
        }
        foreach (['specialty', 'specialtiesIndex'] as $h) {
            if ($et = $entries->getEntryTypeByHandle($h)) {
                $entries->deleteEntryType($et);
                $this->stdout("  removed entry type $h\n");
            }
        }
        $fields = Craft::$app->getFields();
        foreach (['specialty', 'hasAmbulatory', 'ambulatoryOnly', 'ambIntro', 'ambProgram', 'ambPhones', 'ambSchedule', 'ambServices'] as $h) {
            if ($f = $fields->getFieldByHandle($h)) {
                $fields->deleteField($f);
                $this->stdout("  removed field $h\n");
            }
        }
    }

    // ------------------------------------------------------------------ helpers

    private function field(string $class, string $handle, string $name, array $config = []): FieldInterface
    {
        $fieldsService = Craft::$app->getFields();
        $existing = $fieldsService->getFieldByHandle($handle);
        if ($existing) {
            return $this->fields[$handle] = $existing;
        }
        /** @var FieldInterface $field */
        $field = $fieldsService->createField(['type' => $class, 'handle' => $handle, 'name' => $name] + $config);
        if (!$fieldsService->saveField($field)) {
            throw new \RuntimeException("Field $handle: " . json_encode($field->getErrors()));
        }
        $this->stdout("  field $handle\n");
        return $this->fields[$handle] = $field;
    }

    /**
     * @param array<string, string[]> $tabs tab name => field handles
     */
    private function entryType(string $handle, string $name, array $tabs, bool $hasTitle = true, ?string $titleFormat = null, bool $updateLayout = false): EntryType
    {
        $entries = Craft::$app->getEntries();
        $et = $entries->getEntryTypeByHandle($handle);
        if ($et && !$updateLayout) {
            return $et;
        }
        $et ??= new EntryType(['handle' => $handle, 'name' => $name]);
        $et->hasTitleField = $hasTitle;
        $et->titleFormat = $hasTitle ? null : ($titleFormat ?? '{heading ?: "' . $name . '"}');
        $et->showSlugField = $hasTitle;

        $layout = new FieldLayout(['type' => Entry::class]);
        $tabModels = [];
        $first = true;
        foreach ($tabs as $tabName => $handles) {
            $tab = new FieldLayoutTab(['name' => $tabName, 'layout' => $layout]);
            $els = [];
            if ($first && $hasTitle) {
                $els[] = new EntryTitleField();
            }
            foreach ($handles as $h) {
                $els[] = new CustomField($this->fields[$h] ?? Craft::$app->getFields()->getFieldByHandle($h));
            }
            $tab->setElements($els);
            $tabModels[] = $tab;
            $first = false;
        }
        $layout->setTabs($tabModels);
        $et->setFieldLayout($layout);
        if (!$entries->saveEntryType($et)) {
            throw new \RuntimeException("Entry type $handle: " . json_encode($et->getErrors()));
        }
        $this->stdout("  entry type $handle\n");
        return $et;
    }

    /** @param EntryType[] $types */
    private function section(string $handle, string $name, string $type, ?string $uri, ?string $template, array $types): Section
    {
        $entries = Craft::$app->getEntries();
        if ($s = $entries->getSectionByHandle($handle)) {
            $have = array_map(fn($t) => $t->handle, $s->getEntryTypes());
            $want = array_map(fn($t) => $t->handle, $types);
            if ($have !== $want) {
                $s->setEntryTypes($types);
                if (!$entries->saveSection($s)) {
                    throw new \RuntimeException("Section $handle: " . json_encode($s->getErrors()));
                }
                $this->stdout("  section $handle: entry types updated\n");
            }
            return $s;
        }
        $siteSettings = [];
        foreach (Craft::$app->getSites()->getAllSites() as $site) {
            $siteSettings[$site->id] = new Section_SiteSettings([
                'siteId' => $site->id,
                'enabledByDefault' => true,
                'hasUrls' => $uri !== null,
                'uriFormat' => $uri,
                'template' => $template,
            ]);
        }
        $section = new Section([
            'name' => $name,
            'handle' => $handle,
            'type' => $type,
            'siteSettings' => $siteSettings,
            'enableVersioning' => true,
            'propagationMethod' => Section::PROPAGATION_METHOD_ALL,
        ]);
        if ($type === Section::TYPE_STRUCTURE) {
            $section->maxLevels = $handle === 'pages' ? 2 : 1;
        }
        $section->setEntryTypes($types);
        if (!$entries->saveSection($section)) {
            throw new \RuntimeException("Section $handle: " . json_encode($section->getErrors()));
        }
        $this->stdout("  section $handle\n");
        return $section;
    }

    /** @param array<string, string[]> $tabs */
    private function globalSet(string $handle, string $name, array $tabs): void
    {
        $globals = Craft::$app->getGlobals();
        $set = $globals->getSetByHandle($handle) ?? new GlobalSet(['name' => $name, 'handle' => $handle]);
        $layout = new FieldLayout(['type' => GlobalSet::class]);
        $tabModels = [];
        foreach ($tabs as $tabName => $handles) {
            $tab = new FieldLayoutTab(['name' => $tabName, 'layout' => $layout]);
            $tab->setElements(array_map(fn($h) => new CustomField($this->fields[$h]), $handles));
            $tabModels[] = $tab;
        }
        $layout->setTabs($tabModels);
        $set->setFieldLayout($layout);
        if (!$globals->saveSet($set)) {
            throw new \RuntimeException("Global set $handle: " . json_encode($set->getErrors()));
        }
        $this->stdout("  global set $handle\n");
    }

    private function ensureVolume(): Volume
    {
        $volumes = Craft::$app->getVolumes();
        if ($v = $volumes->getVolumeByHandle('uploads')) {
            return $v;
        }
        $fsService = Craft::$app->getFs();
        if (!$fsService->getFilesystemByHandle('uploads')) {
            $fs = $fsService->createFilesystem([
                'type' => Local::class, 'name' => 'Fișiere', 'handle' => 'uploads',
                'hasUrls' => true, 'url' => '@web/uploads', 'path' => '@webroot/uploads',
            ]);
            if (!$fsService->saveFilesystem($fs)) {
                throw new \RuntimeException('Filesystem: ' . json_encode($fs->getErrors()));
            }
        }
        $volume = new Volume(['name' => 'Fișiere', 'handle' => 'uploads']);
        $volume->setFsHandle('uploads');
        if (!$volumes->saveVolume($volume)) {
            throw new \RuntimeException('Volume: ' . json_encode($volume->getErrors()));
        }
        $this->stdout("  volume uploads\n");
        return $volume;
    }
}
