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
 * Safe to re-run: anything that already exists is left alone. The result is
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

        // Sections that other fields relate to must exist first.
        $specialties = $this->section('specialties', 'Specialități medicale', Section::TYPE_STRUCTURE, 'service/{slug}', '_specialties/entry', [
            $this->entryType('specialty', 'Specialitate', [
                'Conținut' => ['iconName', 'summary', 'beds', 'body', 'contentBlocks', 'equipment', 'gallery'],
                'Program și contact' => ['hours', 'phones', 'relatedLinks'],
                'Ambulatoriu' => ['hasAmbulatory', 'ambulatoryOnly', 'ambIntro', 'ambProgram', 'ambPhones', 'ambSchedule', 'ambServices'],
                'Tarife' => [],
            ]),
        ]);
        $priceGroups = $this->section('priceGroups', 'Tarife', Section::TYPE_STRUCTURE, null, null, [
            $this->entryType('priceGroup', 'Grupă de tarife', ['Conținut' => ['priceItems']]),
        ]);
        $this->field(Entries::class, 'priceGroup', 'Grupă de tarife', [
            'sources' => ['section:' . $priceGroups->uid], 'maxRelations' => 1,
            'instructions' => 'Tarifele afișate pe pagina specialității.',
        ]);
        $this->field(Entries::class, 'specialty', 'Specialitate', [
            'sources' => ['section:' . $specialties->uid], 'maxRelations' => 1,
        ]);
        // Now that priceGroup exists, add it to the specialty layout's "Tarife" tab.
        $this->entryType('specialty', 'Specialitate', [
            'Conținut' => ['iconName', 'summary', 'beds', 'body', 'contentBlocks', 'equipment', 'gallery'],
            'Program și contact' => ['hours', 'phones', 'relatedLinks'],
            'Ambulatoriu' => ['hasAmbulatory', 'ambulatoryOnly', 'ambIntro', 'ambProgram', 'ambPhones', 'ambSchedule', 'ambServices'],
            'Tarife' => ['priceGroup'],
        ], true, null, true);

        $this->section('doctors', 'Medici', Section::TYPE_STRUCTURE, 'team/{slug}', '_doctors/entry', [
            $this->entryType('doctor', 'Medic', ['Conținut' => ['specialty', 'grade', 'role', 'photo', 'bio']]),
        ]);
        $this->section('news', 'Noutăți', Section::TYPE_CHANNEL, 'noutati/{slug}', '_news/entry', [
            $this->entryType('newsItem', 'Articol', ['Conținut' => ['category', 'showDate', 'excerpt', 'image', 'body', 'attachment', 'linkUrl']]),
        ]);
        $pages = null;
        $pageLayout = ['Conținut' => ['heading', 'body', 'contentBlocks'], 'Navigare' => ['hideFromNav', 'navGroup']];
        $pageTypes = [
            $this->entryType('page', 'Pagină', $pageLayout),
            $this->entryType('specialtiesIndex', 'Listă specialități', $pageLayout),
            $this->entryType('ambulatoryIndex', 'Listă ambulatoriu', $pageLayout),
            $this->entryType('doctorsIndex', 'Listă medici', $pageLayout),
            $this->entryType('newsIndex', 'Listă noutăți', $pageLayout),
            $this->entryType('pricesPage', 'Pagină tarife', $pageLayout),
            $this->entryType('publicInterest', 'Pagină interes public', $pageLayout),
            $this->entryType('contactPage', 'Pagină contact', $pageLayout),
        ];
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

        // Specialty
        $text('beds', 'Paturi');
        $list('hours', 'Program');
        $list('phones', 'Telefoane');
        $list('equipment', 'Dotări');
        $switch('hasAmbulatory', 'Are cabinet în ambulatoriu');
        $switch('ambulatoryOnly', 'Doar ambulatoriu', ['instructions' => 'Ascunde din lista secțiilor (apare doar la Ambulatoriu).']);
        $multi('ambIntro', 'Ambulatoriu – descriere');
        $list('ambProgram', 'Ambulatoriu – program');
        $list('ambPhones', 'Ambulatoriu – telefoane');
        $table('ambSchedule', 'Ambulatoriu – program medici', [['doctor', 'Medic'], ['program', 'Program']]);
        $list('ambServices', 'Ambulatoriu – servicii');

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
        return [
            $this->entryType('blockText', 'Text', ['Conținut' => ['heading', 'body']], false),
            $this->entryType('blockMedia', 'Text cu imagine', ['Conținut' => ['heading', 'body', 'image']], false),
            $this->entryType('blockList', 'Listă', ['Conținut' => ['heading', 'listItems']], false),
            $this->entryType('blockTable', 'Tabel', ['Conținut' => ['heading', 'tableHeadings', 'tableRows']], false),
            $this->entryType('blockAccordion', 'Acordeon', ['Conținut' => ['heading', 'accordionItems']], false),
            $this->entryType('blockDocuments', 'Documente', ['Conținut' => ['heading', 'documents', 'docLinks']], false),
            $this->entryType('blockCards', 'Carduri', ['Conținut' => ['heading', 'cardItems']], false),
            $this->entryType('blockGallery', 'Galerie', ['Conținut' => ['heading', 'gallery']], false),
            $this->entryType('blockNotice', 'Atenționare', ['Conținut' => ['note']], false),
        ];
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
        if ($globals->getSetByHandle($handle)) {
            return;
        }
        $set = new GlobalSet(['name' => $name, 'handle' => $handle]);
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
